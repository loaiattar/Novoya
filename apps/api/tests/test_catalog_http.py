from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.public import current_user
from novoya_api.catalog.application.use_cases.get_offer_detail import GetOfferDetail
from novoya_api.catalog.application.use_cases.list_extras import ListExtras
from novoya_api.catalog.application.use_cases.list_reviews import ListReviews
from novoya_api.catalog.domain import Extra, ExtraPricing, PriceUnit, Review
from novoya_api.catalog.presentation.http.dependencies import (
    get_get_offer_detail,
    get_list_destinations,
    get_list_extras,
    get_list_reviews,
)
from novoya_api.main import create_app
from tests.test_catalog_admin import FakeOffers, FakePartners, _offer, _partner, signed_in_as


class FakeListDestinations:
    def __init__(self, places: list[tuple[str, str]]) -> None:
        self.places = places

    async def __call__(self) -> list[tuple[str, str]]:
        return list(self.places)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_destinations_returns_covered_places(app, client):
    app.dependency_overrides[get_list_destinations] = lambda: FakeListDestinations(
        [("France", "Biarritz"), ("Greece", "Chania"), ("Morocco", "Marrakech")]
    )
    response = await client.get("/destinations")
    assert response.status_code == 200
    assert response.json() == [
        {"country": "France", "city": "Biarritz"},
        {"country": "Greece", "city": "Chania"},
        {"country": "Morocco", "city": "Marrakech"},
    ]


async def test_destinations_can_be_empty(app, client):
    app.dependency_overrides[get_list_destinations] = lambda: FakeListDestinations([])
    response = await client.get("/destinations")
    assert response.status_code == 200
    assert response.json() == []


async def test_destinations_updates_when_coverage_changes(app, client):
    fake = FakeListDestinations([("Greece", "Chania"), ("Morocco", "Marrakech")])
    app.dependency_overrides[get_list_destinations] = lambda: fake

    first = await client.get("/destinations")
    assert [row["city"] for row in first.json()] == ["Chania", "Marrakech"]

    fake.places = [("Greece", "Chania")]
    second = await client.get("/destinations")
    assert second.json() == [{"country": "Greece", "city": "Chania"}]


# Offer detail


def _priced_offer(partner, **overrides: object):
    values: dict[str, object] = {
        "price_eur": 85,
        "price_unit": PriceUnit("person/night"),
        "opening_months": (5, 6, 9),
        "conditions": "Breakfast included",
        "restrictions": "No smoking",
        "cancellation": "Free up to 7 days before",
        "confirmation_delay_hours": 24,
    }
    values.update(overrides)
    return _offer(partner, **values)


def _offer_detail(app, *pairs) -> None:
    partners = FakePartners([partner for partner, _offer in pairs])
    offers = FakeOffers([offer for _partner, offer in pairs])
    offers.partners = partners
    app.dependency_overrides[get_get_offer_detail] = lambda: GetOfferDetail(offers)


async def test_offer_detail_shows_the_price_months_and_terms(app, client):
    partner = _partner()
    offer = _priced_offer(partner)
    _offer_detail(app, (partner, offer))
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT)

    response = await client.get(f"/offers/{offer.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(offer.id)
    assert body["title"] == "Sea room"
    assert body["price_eur"] == 85
    assert body["price_unit"] == "person/night"
    assert body["opening_months"] == [5, 6, 9]
    assert body["conditions"] == "Breakfast included"
    assert body["restrictions"] == "No smoking"
    assert body["cancellation"] == "Free up to 7 days before"
    assert body["confirmation_delay_hours"] == 24
    assert (body["country"], body["city"]) == ("Greece", "Chania")


async def test_offer_detail_never_shows_the_partner(app, client):
    partner = _partner()
    offer = _priced_offer(partner)
    _offer_detail(app, (partner, offer))
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT)

    response = await client.get(f"/offers/{offer.id}")

    assert not any(key.startswith("partner") for key in response.json())
    assert partner.name not in response.text
    assert partner.contact_email not in response.text


@pytest.mark.parametrize(
    ("partner_active", "offer_active"),
    [(True, False), (False, True)],
    ids=["inactive offer", "inactive partner"],
)
async def test_offer_detail_of_an_unlisted_offer_is_404(app, client, partner_active, offer_active):
    partner = _partner(active=partner_active)
    offer = _priced_offer(partner, active=offer_active)
    _offer_detail(app, (partner, offer))
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT)

    response = await client.get(f"/offers/{offer.id}")

    assert response.status_code == 404
    assert response.json()["code"] == "offer_not_found"


async def test_offer_detail_of_an_unknown_offer_is_404(app, client):
    _offer_detail(app)
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT)

    response = await client.get(f"/offers/{uuid4()}")

    assert response.status_code == 404


async def test_offer_detail_needs_a_session(app, client):
    partner = _partner()
    offer = _priced_offer(partner)
    _offer_detail(app, (partner, offer))

    assert (await client.get(f"/offers/{offer.id}")).status_code == 401


# Reviews


def _review(country: str, city: str, reviewed_on: date, author: str) -> Review:
    return Review(
        id=uuid4(),
        country=country,
        city=city,
        rating=5,
        reviewed_on=reviewed_on,
        text="A made-up review.",
        author=author,
    )


class FakeReviews:
    def __init__(self, reviews: list[Review]) -> None:
        self.reviews = reviews
        self.calls: list[tuple[str | None, str | None, int]] = []

    async def list_at(self, country: str | None, city: str | None, limit: int) -> list[Review]:
        self.calls.append((country, city, limit))
        return list(self.reviews)


async def test_reviews_are_public(app, client):
    review = _review("Greece", "Chania", date(2026, 6, 1), "Voyageur anonyme")
    reviews = FakeReviews([review])
    app.dependency_overrides[get_list_reviews] = lambda: ListReviews(reviews)

    response = await client.get("/reviews")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(review.id),
            "country": "Greece",
            "city": "Chania",
            "rating": 5,
            "reviewed_on": "2026-06-01",
            "text": "A made-up review.",
            "author": "Voyageur anonyme",
        }
    ]
    assert reviews.calls == [(None, None, 100)]


async def test_reviews_are_filtered_by_destination(app, client):
    reviews = FakeReviews([])
    app.dependency_overrides[get_list_reviews] = lambda: ListReviews(reviews)

    response = await client.get("/reviews", params={"country": "Greece", "city": "Chania"})

    assert response.status_code == 200
    assert reviews.calls == [("Greece", "Chania", 100)]


# Extras


class FakeExtras:
    def __init__(self, extras: list[Extra]) -> None:
        self.extras = extras

    async def list_active(self) -> list[Extra]:
        return [extra for extra in self.extras if extra.active]


def _extra(extra_id: UUID, label: str, active: bool = True) -> Extra:
    return Extra(
        id=extra_id,
        category="transport",
        label=label,
        description="One more bag in the hold",
        pricing=ExtraPricing("supplement"),
        supplement_eur=25,
        unit="par bagage",
        constraints=("Ask before the trip",),
        active=active,
    )


async def test_extras_need_a_session(app, client):
    app.dependency_overrides[get_list_extras] = lambda: ListExtras(FakeExtras([]))

    assert (await client.get("/extras")).status_code == 401


async def test_extras_list_the_active_ones_for_a_signed_in_user(app, client):
    bag = _extra(uuid4(), "Extra bag")
    extras = FakeExtras([bag, _extra(uuid4(), "Retired option", active=False)])
    app.dependency_overrides[get_list_extras] = lambda: ListExtras(extras)
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT)

    response = await client.get("/extras")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(bag.id),
            "category": "transport",
            "label": "Extra bag",
            "description": "One more bag in the hold",
            "pricing": "supplement",
            "supplement_eur": 25,
            "unit": "par bagage",
            "constraints": ["Ask before the trip"],
        }
    ]


def test_catalog_read_routes_are_documented(app):
    paths = app.openapi()["paths"]
    assert paths["/offers/{offer_id}"]["get"]["operationId"] == "getOffer"
    assert paths["/reviews"]["get"]["operationId"] == "listReviews"
    assert paths["/extras"]["get"]["operationId"] == "listExtras"
