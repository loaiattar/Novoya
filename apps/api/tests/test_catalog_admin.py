"""Admin partners and offers: use cases on fakes, HTTP with a signed-in agent."""

from collections.abc import AsyncIterator, Sequence
from datetime import date
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.accounts.public import current_user
from novoya_api.catalog.application.use_cases.create_offer import CreateOffer, CreateOfferCommand
from novoya_api.catalog.application.use_cases.create_partner import (
    CreatePartner,
    CreatePartnerCommand,
)
from novoya_api.catalog.application.use_cases.list_all_extras import ListAllExtras
from novoya_api.catalog.application.use_cases.list_all_reviews import ListAllReviews
from novoya_api.catalog.application.use_cases.list_offers import ListOffers
from novoya_api.catalog.application.use_cases.list_partners import ListPartners
from novoya_api.catalog.application.use_cases.update_extra import UpdateExtra, UpdateExtraCommand
from novoya_api.catalog.application.use_cases.update_offer import UpdateOffer, UpdateOfferCommand
from novoya_api.catalog.application.use_cases.update_partner import (
    UpdatePartner,
    UpdatePartnerCommand,
)
from novoya_api.catalog.application.use_cases.update_review import (
    UpdateReview,
    UpdateReviewCommand,
)
from novoya_api.catalog.domain import (
    Extra,
    ExtraNotFound,
    ExtraPricing,
    ImportedRow,
    InvalidOffer,
    Offer,
    OfferKind,
    OfferNotFound,
    Partner,
    PartnerKind,
    PartnerNotFound,
    PriceUnit,
    Review,
    ReviewNotFound,
)
from novoya_api.catalog.presentation.http.dependencies import (
    get_create_offer,
    get_create_partner,
    get_list_all_extras,
    get_list_all_reviews,
    get_list_offers,
    get_list_partners,
    get_update_extra,
    get_update_offer,
    get_update_partner,
    get_update_review,
)
from novoya_api.main import create_app
from novoya_api.shared.domain.errors import Conflict
from novoya_api.shared.domain.value_objects import Locale

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
SEASON = (date(2026, 4, 1), date(2026, 10, 31))


class FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


class FakePartners:
    def __init__(self, partners: list[Partner] | None = None) -> None:
        self.by_id = {partner.id: partner for partner in partners or []}

    async def list_all(self) -> list[Partner]:
        return sorted(self.by_id.values(), key=lambda partner: (partner.name, str(partner.id)))

    async def get(self, partner_id: UUID) -> Partner | None:
        return self.by_id.get(partner_id)

    async def add(self, partner: Partner) -> None:
        self.by_id[partner.id] = partner

    async def save(self, partner: Partner) -> None:
        self.by_id[partner.id] = partner


class FakeOffers:
    def __init__(self, offers: list[Offer] | None = None) -> None:
        self.by_id = {offer.id: offer for offer in offers or []}
        self.partners: FakePartners | None = None

    async def list_with_partners(self) -> list[tuple[Offer, Partner]]:
        assert self.partners is not None
        pairs = []
        for offer in self.by_id.values():
            partner = self.partners.by_id[offer.partner_id]
            pairs.append((offer, partner))
        return sorted(pairs, key=lambda item: (item[0].title, str(item[0].id)))

    async def list_listed_destinations(self) -> list[tuple[str, str]]:
        return []

    async def list_at(self, country: str, city: str | None) -> list[tuple[Offer, Partner]]:
        return []

    async def get(self, offer_id: UUID) -> Offer | None:
        return self.by_id.get(offer_id)

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[tuple[Offer, Partner]]:
        assert self.partners is not None
        pairs = []
        for offer_id in ids:
            offer = self.by_id.get(offer_id)
            if offer is None:
                continue
            pairs.append((offer, self.partners.by_id[offer.partner_id]))
        return pairs

    async def add(self, offer: Offer) -> None:
        self.by_id[offer.id] = offer

    async def save(self, offer: Offer) -> None:
        self.by_id[offer.id] = offer


class FakeExtras:
    def __init__(self, extras: list[Extra] | None = None) -> None:
        self.by_id = {extra.id: extra for extra in extras or []}

    async def list_all(self) -> list[Extra]:
        return sorted(self.by_id.values(), key=lambda extra: (extra.label, str(extra.id)))

    async def list_active(self) -> list[Extra]:
        return [extra for extra in await self.list_all() if extra.active and not extra.hidden]

    async def list_active_by_ids(self, ids: Sequence[UUID]) -> list[Extra]:
        return [self.by_id[i] for i in ids if i in self.by_id and not self.by_id[i].hidden]

    async def get(self, extra_id: UUID) -> Extra | None:
        return self.by_id.get(extra_id)

    async def save(self, extra: Extra) -> None:
        self.by_id[extra.id] = extra


class FakeReviews:
    def __init__(self, reviews: list[Review] | None = None) -> None:
        self.by_id = {review.id: review for review in reviews or []}

    async def list_at(self, country: str | None, city: str | None, limit: int) -> list[Review]:
        shown = [review for review in self.by_id.values() if not review.hidden]
        shown.sort(key=lambda review: (review.reviewed_on, review.id), reverse=True)
        return shown[:limit]

    async def list_all(self) -> list[Review]:
        return sorted(
            self.by_id.values(),
            key=lambda review: (review.reviewed_on, str(review.id)),
            reverse=True,
        )

    async def get(self, review_id: UUID) -> Review | None:
        return self.by_id.get(review_id)

    async def save(self, review: Review) -> None:
        self.by_id[review.id] = review


def _review(**overrides: object) -> Review:
    values: dict[str, object] = {
        "id": uuid4(),
        "country": "Greece",
        "city": "Chania",
        "rating": 5,
        "reviewed_on": date(2026, 6, 1),
        "text": "A made-up stay by the sea.",
        "author": "Zélie Q.",
    }
    values.update(overrides)
    return Review(**values)  # type: ignore[arg-type]


def _extra(**overrides: object) -> Extra:
    values: dict[str, object] = {
        "id": uuid4(),
        "category": "comfort",
        "label": "Quiet room",
        "description": "Away from the street",
        "pricing": ExtraPricing.INCLUDED,
        "supplement_eur": None,
        "unit": "par séjour",
        "constraints": (),
        "active": True,
    }
    values.update(overrides)
    return Extra(**values)  # type: ignore[arg-type]


def _partner(**overrides: object) -> Partner:
    values: dict[str, object] = {
        "id": uuid4(),
        "name": "Elounda Bay House",
        "kind": PartnerKind.HOTEL,
        "country": "Greece",
        "city": "Chania",
        "contact_email": "stay@elounda.example",
        "contact_phone": "+30 28210 00001",
        "active": True,
    }
    values.update(overrides)
    return Partner(**values)  # type: ignore[arg-type]


def _offer(partner: Partner, **overrides: object) -> Offer:
    values: dict[str, object] = {
        "id": uuid4(),
        "partner_id": partner.id,
        "kind": OfferKind.HOTEL,
        "title": "Sea room",
        "description": "A room",
        "country": "Greece",
        "city": "Chania",
        "min_persons": 2,
        "max_persons": 4,
        "available_from": SEASON[0],
        "available_to": SEASON[1],
        "tags": ("style:beach",),
        "featured": False,
        "active": True,
    }
    values.update(overrides)
    return Offer(**values)  # type: ignore[arg-type]


NEW_PARTNER = CreatePartnerCommand(
    name="  New Riad ",
    kind=PartnerKind.HOTEL,
    country="morocco",
    city="marrakech",
    contact_email="  hello@riad.example ",
    contact_phone=" +212 000 ",
)


# Use cases


async def test_create_partner_title_cases_the_place_and_strips_fields():
    partners = FakePartners()
    created = await CreatePartner(partners, FakeUow())(NEW_PARTNER)

    assert created.name == "New Riad"
    assert created.country == "Morocco"
    assert created.city == "Marrakech"
    assert created.contact_email == "hello@riad.example"
    assert partners.by_id[created.id] == created


async def test_list_partners_includes_inactive_ones():
    closed = _partner(name="Closed", active=False)
    partners = FakePartners([closed, _partner(name="Open")])

    listed = await ListPartners(partners)()

    assert [partner.name for partner in listed] == ["Closed", "Open"]


async def test_update_partner_can_deactivate_without_touching_offers():
    partner = _partner()
    partners = FakePartners([partner])

    updated = await UpdatePartner(partners, FakeUow())(
        UpdatePartnerCommand(partner_id=partner.id, active=False)
    )

    assert updated.active is False
    assert updated.name == partner.name


async def test_update_missing_partner_is_not_found():
    with pytest.raises(PartnerNotFound):
        await UpdatePartner(FakePartners(), FakeUow())(UpdatePartnerCommand(partner_id=uuid4()))


async def test_create_offer_needs_an_existing_partner():
    with pytest.raises(PartnerNotFound):
        await CreateOffer(FakeOffers(), FakePartners(), FakeUow())(
            CreateOfferCommand(
                partner_id=uuid4(),
                kind=OfferKind.HOTEL,
                title="Stay",
                description="A room",
                country="Greece",
                city="Chania",
                min_persons=1,
                max_persons=2,
                available_from=SEASON[0],
                available_to=SEASON[1],
                tags=("style:beach",),
            )
        )


async def test_create_offer_normalizes_tags_and_place():
    partner = _partner()
    offers = FakeOffers()
    offers.partners = FakePartners([partner])

    created = await CreateOffer(offers, offers.partners, FakeUow())(
        CreateOfferCommand(
            partner_id=partner.id,
            kind=OfferKind.HOTEL,
            title="Stay",
            description="A room",
            country="greece",
            city="chania",
            min_persons=2,
            max_persons=4,
            available_from=SEASON[0],
            available_to=SEASON[1],
            tags=("STYLE:Beach", "style:beach"),
        )
    )

    assert created.country == "Greece"
    assert created.tags == ("style:beach",)


async def test_create_offer_rejects_inverted_person_limits():
    partner = _partner()
    with pytest.raises(InvalidOffer):
        await CreateOffer(FakeOffers(), FakePartners([partner]), FakeUow())(
            CreateOfferCommand(
                partner_id=partner.id,
                kind=OfferKind.HOTEL,
                title="Stay",
                description="A room",
                country="Greece",
                city="Chania",
                min_persons=4,
                max_persons=2,
                available_from=SEASON[0],
                available_to=SEASON[1],
                tags=(),
            )
        )


async def test_update_offer_can_deactivate():
    partner = _partner()
    offer = _offer(partner)
    offers = FakeOffers([offer])
    offers.partners = FakePartners([partner])

    updated = await UpdateOffer(offers, offers.partners, FakeUow())(
        UpdateOfferCommand(offer_id=offer.id, active=False)
    )

    assert updated.active is False
    assert updated.title == offer.title


async def test_update_missing_offer_is_not_found():
    with pytest.raises(OfferNotFound):
        await UpdateOffer(FakeOffers(), FakePartners(), FakeUow())(
            UpdateOfferCommand(offer_id=uuid4())
        )


async def test_list_offers_includes_inactive_ones():
    partner = _partner()
    hidden = _offer(partner, title="Hidden", active=False)
    shown = _offer(partner, title="Shown")
    offers = FakeOffers([hidden, shown])
    offers.partners = FakePartners([partner])

    listed = await ListOffers(offers)()

    assert [offer.title for offer in listed] == ["Hidden", "Shown"]


async def test_list_offers_of_one_partner_leaves_out_the_others():
    riad = _partner(name="Riad Lune")
    lodge = _partner(name="Lodge Nord")
    offers = FakeOffers(
        [
            _offer(riad, title="Patio room"),
            _offer(lodge, title="Cabin"),
            _offer(riad, title="Roof suite", active=False),
        ]
    )
    offers.partners = FakePartners([riad, lodge])

    listed = await ListOffers(offers)(partner_id=riad.id)

    assert [offer.title for offer in listed] == ["Patio room", "Roof suite"]


async def test_list_offers_without_a_partner_keeps_every_offer():
    riad = _partner(name="Riad Lune")
    lodge = _partner(name="Lodge Nord")
    offers = FakeOffers([_offer(riad, title="Patio room"), _offer(lodge, title="Cabin")])
    offers.partners = FakePartners([riad, lodge])

    listed = await ListOffers(offers)(partner_id=None)

    assert [offer.title for offer in listed] == ["Cabin", "Patio room"]


# Rows imported from DÉTOUR: DÉTOUR owns their content, Novoya only featured and hidden.


def test_an_imported_row_error_is_a_409_conflict_with_a_stable_code():
    assert issubclass(ImportedRow, Conflict)
    assert ImportedRow.code == "imported_row"


@pytest.mark.parametrize(
    "change",
    [
        {"name": "Renamed"},
        {"kind": PartnerKind.GUIDE},
        {"city": "Heraklion"},
        {"contact_email": "new@elounda.example"},
        {"contact_phone": "+30 000"},
        {"active": False},
    ],
)
async def test_the_content_of_an_imported_partner_cannot_change(change):
    partner = _partner(imported=True, contact_phone=None)
    partners = FakePartners([partner])

    with pytest.raises(ImportedRow, match="DÉTOUR"):
        await UpdatePartner(partners, FakeUow())(
            UpdatePartnerCommand(partner_id=partner.id, **change)
        )

    assert partners.by_id[partner.id] == partner


async def test_an_imported_partner_can_be_hidden():
    partner = _partner(imported=True)
    partners = FakePartners([partner])

    updated = await UpdatePartner(partners, FakeUow())(
        UpdatePartnerCommand(partner_id=partner.id, hidden=True)
    )

    assert updated.hidden is True
    assert partners.by_id[partner.id].hidden is True


async def test_sending_an_imported_partner_its_own_values_is_not_a_change():
    partner = _partner(imported=True)

    updated = await UpdatePartner(FakePartners([partner]), FakeUow())(
        UpdatePartnerCommand(partner_id=partner.id, name=partner.name, city="chania")
    )

    assert updated == partner


def _imported_offer(**overrides: object) -> tuple[FakeOffers, Offer]:
    partner = _partner(imported=True)
    offer = _offer(partner, price_eur=90, price_unit=PriceUnit.PERSON_NIGHT, **overrides)
    offers = FakeOffers([offer])
    offers.partners = FakePartners([partner])
    return offers, offer


@pytest.mark.parametrize(
    "change",
    [
        {"title": "Renamed"},
        {"description": "Another room"},
        {"tags": ("style:city",)},
        {"max_persons": 6},
        {"available_to": date(2026, 9, 30)},
        {"price_eur": 120},
        {"opening_months": (5, 6)},
        {"conditions": "Pay on arrival"},
        {"active": False},
        {"kind": OfferKind.ACTIVITY},
    ],
)
async def test_the_content_of_an_imported_offer_cannot_change(change):
    offers, offer = _imported_offer()

    with pytest.raises(ImportedRow, match="DÉTOUR"):
        await UpdateOffer(offers, offers.partners, FakeUow())(
            UpdateOfferCommand(offer_id=offer.id, **change)
        )

    assert offers.by_id[offer.id] == offer


async def test_an_imported_offer_can_be_featured_and_hidden():
    offers, offer = _imported_offer()

    updated = await UpdateOffer(offers, offers.partners, FakeUow())(
        UpdateOfferCommand(offer_id=offer.id, featured=True, hidden=True)
    )

    assert (updated.featured, updated.hidden) == (True, True)
    assert updated.title == offer.title


async def test_clearing_the_price_of_an_imported_offer_is_refused():
    offers, offer = _imported_offer()

    with pytest.raises(ImportedRow):
        await UpdateOffer(offers, offers.partners, FakeUow())(
            UpdateOfferCommand(offer_id=offer.id, cleared=frozenset({"price_eur", "price_unit"}))
        )


async def test_an_offer_cannot_be_added_to_an_imported_partner():
    partner = _partner(imported=True)
    offers = FakeOffers()

    with pytest.raises(ImportedRow):
        await CreateOffer(offers, FakePartners([partner]), FakeUow())(
            CreateOfferCommand(
                partner_id=partner.id,
                kind=OfferKind.HOTEL,
                title="Stay",
                description="A room",
                country="Greece",
                city="Chania",
                min_persons=1,
                max_persons=2,
                available_from=SEASON[0],
                available_to=SEASON[1],
                tags=(),
            )
        )

    assert offers.by_id == {}


async def test_a_hand_made_offer_stays_fully_editable():
    partner = _partner()
    offer = _offer(partner)
    offers = FakeOffers([offer])
    offers.partners = FakePartners([partner])

    updated = await UpdateOffer(offers, offers.partners, FakeUow())(
        UpdateOfferCommand(
            offer_id=offer.id,
            title="Renamed",
            active=False,
            hidden=True,
            price_eur=80,
            price_unit=PriceUnit.PERSON_NIGHT,
        )
    )

    assert (updated.title, updated.active, updated.hidden) == ("Renamed", False, True)
    assert (updated.price_eur, updated.price_unit) == (80, PriceUnit.PERSON_NIGHT)


async def test_a_hand_made_partner_stays_fully_editable():
    partner = _partner()

    updated = await UpdatePartner(FakePartners([partner]), FakeUow())(
        UpdatePartnerCommand(partner_id=partner.id, name="Renamed", contact_phone="+30 111")
    )

    assert (updated.name, updated.contact_phone) == ("Renamed", "+30 111")


async def test_the_price_and_months_of_a_hand_made_offer_can_be_cleared():
    partner = _partner()
    offer = _offer(partner, price_eur=90, price_unit=PriceUnit.PERSON_NIGHT, opening_months=(5,))
    offers = FakeOffers([offer])
    offers.partners = FakePartners([partner])

    updated = await UpdateOffer(offers, offers.partners, FakeUow())(
        UpdateOfferCommand(
            offer_id=offer.id, cleared=frozenset({"price_eur", "price_unit", "opening_months"})
        )
    )

    assert (updated.price_eur, updated.price_unit, updated.opening_months) == (None, None, ())


async def test_clearing_the_price_without_its_unit_is_refused():
    partner = _partner()
    offer = _offer(partner, price_eur=90, price_unit=PriceUnit.PERSON_NIGHT)
    offers = FakeOffers([offer])
    offers.partners = FakePartners([partner])

    with pytest.raises(InvalidOffer):
        await UpdateOffer(offers, offers.partners, FakeUow())(
            UpdateOfferCommand(offer_id=offer.id, cleared=frozenset({"price_eur"}))
        )


async def test_an_extra_can_be_hidden_and_shown_again():
    extra = _extra()
    extras = FakeExtras([extra])

    hidden = await UpdateExtra(extras, FakeUow())(UpdateExtraCommand(extra.id, hidden=True))
    assert hidden.hidden is True
    assert await extras.list_active() == []

    shown = await UpdateExtra(extras, FakeUow())(UpdateExtraCommand(extra.id, hidden=False))
    assert shown == extra


async def test_hiding_a_missing_extra_is_not_found():
    with pytest.raises(ExtraNotFound):
        await UpdateExtra(FakeExtras(), FakeUow())(UpdateExtraCommand(uuid4(), hidden=True))


async def test_the_admin_extras_list_includes_hidden_and_inactive_ones():
    extras = FakeExtras(
        [_extra(label="Gone", active=False), _extra(label="Hidden", hidden=True), _extra()]
    )

    listed = await ListAllExtras(extras)()

    assert [extra.label for extra in listed] == ["Gone", "Hidden", "Quiet room"]


async def test_a_review_can_be_hidden_and_shown_again():
    review = _review()
    reviews = FakeReviews([review])

    hidden = await UpdateReview(reviews, FakeUow())(UpdateReviewCommand(review.id, hidden=True))
    assert hidden.hidden is True
    assert await reviews.list_at(None, None, 100) == []
    assert await reviews.list_all() == [hidden]

    shown = await UpdateReview(reviews, FakeUow())(UpdateReviewCommand(review.id, hidden=False))
    assert shown == review


async def test_hiding_a_missing_review_is_not_found():
    with pytest.raises(ReviewNotFound):
        await UpdateReview(FakeReviews(), FakeUow())(UpdateReviewCommand(uuid4(), hidden=True))


async def test_the_admin_reviews_list_includes_hidden_ones():
    hidden = _review(author="Voyageur anonyme", hidden=True, reviewed_on=date(2026, 8, 1))
    shown = _review()

    listed = await ListAllReviews(FakeReviews([shown, hidden]))()

    assert [review.author for review in listed] == ["Voyageur anonyme", "Zélie Q."]


# HTTP


def signed_in_as(role: Role) -> CurrentUserView:
    return CurrentUserView(
        user_id=UserId(USER_ID),
        email=Email("agent@example.com"),
        name=None,
        role=role,
        locale=Locale.EN,
        session_id=USER_ID,
    )


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _as_admin(
    app, partners: FakePartners, offers: FakeOffers | None = None, extras: FakeExtras | None = None
) -> None:
    offers = offers or FakeOffers()
    extras = extras or FakeExtras()
    offers.partners = partners
    uow = FakeUow()
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.ADMIN)
    app.dependency_overrides[get_list_partners] = lambda: ListPartners(partners)
    app.dependency_overrides[get_create_partner] = lambda: CreatePartner(partners, uow)
    app.dependency_overrides[get_update_partner] = lambda: UpdatePartner(partners, uow)
    app.dependency_overrides[get_list_offers] = lambda: ListOffers(offers)
    app.dependency_overrides[get_create_offer] = lambda: CreateOffer(offers, partners, uow)
    app.dependency_overrides[get_update_offer] = lambda: UpdateOffer(offers, partners, uow)
    app.dependency_overrides[get_list_all_extras] = lambda: ListAllExtras(extras)
    app.dependency_overrides[get_update_extra] = lambda: UpdateExtra(extras, uow)


def _as_review_admin(app, reviews: FakeReviews | None = None) -> None:
    reviews = reviews or FakeReviews()
    uow = FakeUow()
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.ADMIN)
    app.dependency_overrides[get_list_all_reviews] = lambda: ListAllReviews(reviews)
    app.dependency_overrides[get_update_review] = lambda: UpdateReview(reviews, uow)


async def test_admin_partners_without_a_session_returns_401(client):
    assert (await client.get("/admin/partners")).status_code == 401
    assert (await client.get("/admin/offers")).status_code == 401
    assert (await client.get("/admin/reviews")).status_code == 401


@pytest.mark.parametrize("role", [Role.CLIENT, Role.AGENT])
async def test_admin_catalog_is_for_admins_only(app, client, role):
    app.dependency_overrides[current_user] = lambda: signed_in_as(role)

    assert (await client.get("/admin/partners")).status_code == 403
    assert (await client.get("/admin/offers")).status_code == 403
    assert (await client.get("/admin/extras")).status_code == 403
    assert (await client.get("/admin/reviews")).status_code == 403


async def test_admin_can_create_list_and_deactivate_a_partner(app, client):
    partners = FakePartners()
    _as_admin(app, partners)

    created = await client.post(
        "/admin/partners",
        json={
            "name": "New Riad",
            "kind": "hotel",
            "country": "morocco",
            "city": "marrakech",
            "contact_email": "hello@riad.example",
            "contact_phone": "+212 000",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["country"] == "Morocco"
    assert body["city"] == "Marrakech"

    listed = await client.get("/admin/partners")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [body["id"]]

    patched = await client.patch(f"/admin/partners/{body['id']}", json={"active": False})
    assert patched.status_code == 200
    assert patched.json()["active"] is False


async def test_admin_can_create_a_partner_without_a_phone(app, client):
    partners = FakePartners()
    _as_admin(app, partners)

    created = await client.post(
        "/admin/partners",
        json={
            "name": "No Phone Lodge",
            "kind": "hotel",
            "country": "Greece",
            "city": "Chania",
            "contact_email": "hello@nophone.example",
        },
    )

    assert created.status_code == 201
    assert created.json()["contact_phone"] is None


async def test_create_partner_without_a_phone_stores_none():
    partners = FakePartners()

    created = await CreatePartner(partners, FakeUow())(
        CreatePartnerCommand(
            name="No Phone Lodge",
            kind=PartnerKind.HOTEL,
            country="Greece",
            city="Chania",
            contact_email="hello@nophone.example",
            contact_phone=None,
        )
    )

    assert created.contact_phone is None


async def test_admin_offer_create_needs_a_partner(app, client):
    _as_admin(app, FakePartners())

    response = await client.post(
        "/admin/offers",
        json={
            "partner_id": str(uuid4()),
            "kind": "hotel",
            "title": "Stay",
            "description": "A room",
            "country": "Greece",
            "city": "Chania",
            "min_persons": 2,
            "max_persons": 4,
            "available_from": "2026-04-01",
            "available_to": "2026-10-31",
            "tags": ["style:beach"],
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "partner_not_found"


async def test_admin_offer_rejects_inverted_person_limits(app, client):
    partner = _partner()
    _as_admin(app, FakePartners([partner]))

    response = await client.post(
        "/admin/offers",
        json={
            "partner_id": str(partner.id),
            "kind": "hotel",
            "title": "Stay",
            "description": "A room",
            "country": "Greece",
            "city": "Chania",
            "min_persons": 4,
            "max_persons": 2,
            "available_from": "2026-04-01",
            "available_to": "2026-10-31",
            "tags": ["style:beach"],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_offer"


async def test_admin_can_create_and_deactivate_an_offer(app, client):
    partner = _partner()
    _as_admin(app, FakePartners([partner]))

    created = await client.post(
        "/admin/offers",
        json={
            "partner_id": str(partner.id),
            "kind": "hotel",
            "title": "Stay",
            "description": "A room",
            "country": "greece",
            "city": "chania",
            "min_persons": 2,
            "max_persons": 4,
            "available_from": "2026-04-01",
            "available_to": "2026-10-31",
            "tags": ["STYLE:Beach"],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["tags"] == ["style:beach"]
    assert body["country"] == "Greece"

    patched = await client.patch(f"/admin/offers/{body['id']}", json={"active": False})
    assert patched.status_code == 200
    assert patched.json()["active"] is False


async def test_editing_an_imported_offer_is_a_409_that_names_detour(app, client):
    offers, offer = _imported_offer()
    _as_admin(app, offers.partners, offers)

    response = await client.patch(f"/admin/offers/{offer.id}", json={"title": "Renamed"})

    assert response.status_code == 409
    assert response.json()["code"] == "imported_row"
    assert "DÉTOUR" in response.json()["detail"]


async def test_an_imported_offer_is_featured_and_hidden_over_http(app, client):
    offers, offer = _imported_offer()
    _as_admin(app, offers.partners, offers)

    response = await client.patch(
        f"/admin/offers/{offer.id}", json={"featured": True, "hidden": True}
    )

    assert response.status_code == 200
    assert (response.json()["featured"], response.json()["hidden"]) == (True, True)


@pytest.mark.parametrize(
    ("field", "value", "accepted"),
    [
        ("price_eur", 1_000_000, True),
        ("price_eur", 1_000_001, False),
        ("confirmation_delay_hours", 720, True),
        ("confirmation_delay_hours", 721, False),
        ("max_persons", 1_000, True),
        ("max_persons", 1_001, False),
    ],
)
async def test_offer_price_and_delay_stay_within_their_columns(app, client, field, value, accepted):
    partner = _partner()
    offers = FakeOffers([])
    offers.partners = FakePartners([partner])
    _as_admin(app, offers.partners, offers)
    body = {
        "partner_id": str(partner.id),
        "kind": "hotel",
        "title": "Stay",
        "description": "A room",
        "country": "greece",
        "city": "chania",
        "min_persons": 2,
        "max_persons": 4,
        "available_from": "2026-04-01",
        "available_to": "2026-10-31",
        "price_unit": "person/night",
        "price_eur": 90,
        field: value,
    }

    created = await client.post("/admin/offers", json=body)

    assert created.status_code == (201 if accepted else 422)


@pytest.mark.parametrize(
    ("field", "value"),
    [("price_eur", 1_000_001), ("confirmation_delay_hours", 721), ("max_persons", 1_001)],
)
async def test_an_offer_patch_beyond_the_columns_is_a_422(app, client, field, value):
    partner = _partner()
    offer = _offer(partner, price_eur=90, price_unit=PriceUnit.PERSON_NIGHT)
    offers = FakeOffers([offer])
    _as_admin(app, FakePartners([partner]), offers)

    response = await client.patch(f"/admin/offers/{offer.id}", json={field: value})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_editing_an_imported_partner_is_a_409(app, client):
    partner = _partner(imported=True)
    _as_admin(app, FakePartners([partner]))

    response = await client.patch(f"/admin/partners/{partner.id}", json={"name": "Renamed"})

    assert response.status_code == 409
    assert response.json()["code"] == "imported_row"


async def test_an_imported_partner_is_hidden_over_http(app, client):
    partner = _partner(imported=True)
    _as_admin(app, FakePartners([partner]))

    response = await client.patch(f"/admin/partners/{partner.id}", json={"hidden": True})

    assert response.status_code == 200
    assert (response.json()["hidden"], response.json()["imported"]) == (True, True)


async def test_a_null_price_and_unit_clear_the_price(app, client):
    partner = _partner()
    offer = _offer(partner, price_eur=90, price_unit=PriceUnit.PERSON_NIGHT, opening_months=(5,))
    offers = FakeOffers([offer])
    _as_admin(app, FakePartners([partner]), offers)

    response = await client.patch(
        f"/admin/offers/{offer.id}",
        json={"price_eur": None, "price_unit": None, "opening_months": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["price_eur"], body["price_unit"], body["opening_months"]) == (None, None, [])


async def test_a_null_price_alone_is_a_422(app, client):
    partner = _partner()
    offer = _offer(partner, price_eur=90, price_unit=PriceUnit.PERSON_NIGHT)
    _as_admin(app, FakePartners([partner]), FakeOffers([offer]))

    response = await client.patch(f"/admin/offers/{offer.id}", json={"price_eur": None})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_offer"


async def test_an_absent_price_is_unchanged(app, client):
    partner = _partner()
    offer = _offer(partner, price_eur=90, price_unit=PriceUnit.PERSON_NIGHT, opening_months=(5,))
    _as_admin(app, FakePartners([partner]), FakeOffers([offer]))

    response = await client.patch(f"/admin/offers/{offer.id}", json={"title": "Renamed"})

    assert response.status_code == 200
    body = response.json()
    assert (body["price_eur"], body["price_unit"], body["opening_months"]) == (
        90,
        "person/night",
        [5],
    )


async def test_an_agent_hides_an_extra_over_http(app, client):
    extra = _extra()
    _as_admin(app, FakePartners(), extras=FakeExtras([extra]))

    response = await client.patch(f"/admin/extras/{extra.id}", json={"hidden": True})

    assert response.status_code == 200
    assert response.json()["hidden"] is True
    listed = await client.get("/admin/extras")
    assert [(row["id"], row["hidden"], row["active"]) for row in listed.json()] == [
        (str(extra.id), True, True)
    ]


async def test_the_content_of_an_extra_cannot_be_patched(app, client):
    extra = _extra()
    _as_admin(app, FakePartners(), extras=FakeExtras([extra]))

    response = await client.patch(f"/admin/extras/{extra.id}", json={"label": "Renamed"})

    assert response.status_code == 422


async def test_an_admin_hides_a_review_over_http(app, client):
    review = _review()
    _as_review_admin(app, FakeReviews([review]))

    response = await client.patch(f"/admin/reviews/{review.id}", json={"hidden": True})

    assert response.status_code == 200
    assert response.json()["hidden"] is True
    listed = await client.get("/admin/reviews")
    assert [(row["id"], row["hidden"], row["author"]) for row in listed.json()] == [
        (str(review.id), True, "Zélie Q.")
    ]


async def test_the_content_of_a_review_cannot_be_patched(app, client):
    review = _review()
    _as_review_admin(app, FakeReviews([review]))

    response = await client.patch(f"/admin/reviews/{review.id}", json={"text": "Changed"})

    assert response.status_code == 422


async def test_admin_reviews_need_an_admin(app, client):
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.AGENT)

    assert (await client.get("/admin/reviews")).status_code == 403
    hidden = await client.patch(f"/admin/reviews/{uuid4()}", json={"hidden": True})
    assert hidden.status_code == 403


async def test_admin_offers_filtered_by_partner_over_http(app, client):
    riad = _partner(name="Riad Lune")
    lodge = _partner(name="Lodge Nord")
    patio = _offer(riad, title="Patio room")
    offers = FakeOffers([patio, _offer(lodge, title="Cabin")])
    _as_admin(app, FakePartners([riad, lodge]), offers)

    response = await client.get("/admin/offers", params={"partner_id": str(riad.id)})

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [str(patio.id)]


async def test_admin_offers_of_an_unknown_partner_is_an_empty_list(app, client):
    riad = _partner(name="Riad Lune")
    _as_admin(app, FakePartners([riad]), FakeOffers([_offer(riad)]))

    response = await client.get("/admin/offers", params={"partner_id": str(uuid4())})

    assert response.status_code == 200
    assert response.json() == []


async def test_admin_offers_with_a_malformed_partner_id_is_a_422(app, client):
    riad = _partner(name="Riad Lune")
    _as_admin(app, FakePartners([riad]), FakeOffers([_offer(riad)]))

    response = await client.get("/admin/offers", params={"partner_id": "not-a-uuid"})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


def test_admin_catalog_routes_are_documented(app):
    paths = app.openapi()["paths"]
    assert paths["/admin/partners"]["get"]["operationId"] == "listPartners"
    assert paths["/admin/partners"]["post"]["operationId"] == "createPartner"
    assert paths["/admin/partners/{partner_id}"]["patch"]["operationId"] == "updatePartner"
    assert paths["/admin/offers"]["get"]["operationId"] == "listOffers"
    assert paths["/admin/offers"]["post"]["operationId"] == "createOffer"
    assert paths["/admin/offers/{offer_id}"]["patch"]["operationId"] == "updateOffer"
    assert paths["/admin/extras"]["get"]["operationId"] == "listAllExtras"
    assert paths["/admin/extras/{extra_id}"]["patch"]["operationId"] == "updateExtra"
    assert paths["/admin/reviews"]["get"]["operationId"] == "listAllReviews"
    assert paths["/admin/reviews/{review_id}"]["patch"]["operationId"] == "updateReview"
    assert "409" in paths["/admin/offers/{offer_id}"]["patch"]["responses"]
    offer_params = {
        param["name"]: param for param in paths["/admin/offers"]["get"].get("parameters", [])
    }
    assert offer_params["partner_id"]["in"] == "query"
    assert offer_params["partner_id"]["required"] is False
    responses = paths["/admin/partners"]["get"]["responses"]
    for status in ("401", "403", "422"):
        ref = responses[status]["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ErrorResponse", status
