import inspect
from collections.abc import Sequence
from datetime import date
from uuid import UUID, uuid4

import pytest

from novoya_api.catalog import public
from novoya_api.catalog.application.use_cases.get_offers import GetOffers
from novoya_api.catalog.application.use_cases.list_destinations import ListDestinations
from novoya_api.catalog.application.use_cases.list_tags_at import ListTagsAt
from novoya_api.catalog.domain import Offer, OfferKind, Partner, PartnerKind
from novoya_api.catalog.public import covered_destinations, tags_at

SEASON_START = date(2026, 4, 1)
SEASON_END = date(2026, 10, 31)


def _partner(**overrides: object) -> Partner:
    values: dict[str, object] = {
        "id": uuid4(),
        "name": "Test partner",
        "kind": PartnerKind.HOTEL,
        "country": "Portugal",
        "city": "Lisbon",
        "contact_email": "p@example.com",
        "contact_phone": "+351 000",
        "active": True,
    }
    values.update(overrides)
    return Partner(**values)  # type: ignore[arg-type]


def _offer(partner: Partner, **overrides: object) -> Offer:
    values: dict[str, object] = {
        "id": uuid4(),
        "partner_id": partner.id,
        "kind": OfferKind.HOTEL,
        "title": "Test stay",
        "description": "A room",
        "country": partner.country,
        "city": partner.city,
        "min_persons": 2,
        "max_persons": 4,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ("style:beach", "rhythm:calm"),
        "featured": False,
        "active": True,
    }
    values.update(overrides)
    return Offer(**values)  # type: ignore[arg-type]


class FakeOffers:
    def __init__(self, pairs: list[tuple[Offer, Partner]]) -> None:
        self._pairs = pairs

    async def list_with_partners(self) -> list[tuple[Offer, Partner]]:
        return list(self._pairs)

    async def list_listed_destinations(self) -> list[tuple[str, str]]:
        destinations = {
            (offer.country, offer.city)
            for offer, partner in self._pairs
            if offer.is_listed_with(partner)
        }
        return sorted(destinations)

    async def list_listed_featured(self, limit: int) -> list[Offer]:
        return []

    async def list_at(self, country: str, city: str | None) -> list[tuple[Offer, Partner]]:
        found: list[tuple[Offer, Partner]] = []
        for offer, partner in self._pairs:
            if offer.country.lower() != country.lower():
                continue
            if city is not None and offer.city.lower() != city.lower():
                continue
            found.append((offer, partner))
        return found

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[tuple[Offer, Partner]]:
        by_id = {offer.id: (offer, partner) for offer, partner in self._pairs}
        return [by_id[offer_id] for offer_id in ids if offer_id in by_id]


async def test_covered_destinations_need_a_listed_offer():
    lisbon = _partner(country="Portugal", city="Lisbon")
    porto = _partner(country="Portugal", city="Porto")
    closed = _partner(country="Spain", city="Seville", active=False)
    empty = _partner(country="France", city="Biarritz")
    pairs = [
        (_offer(lisbon), lisbon),
        (_offer(porto), porto),
        (_offer(closed), closed),
        (_offer(empty, active=False), empty),
    ]
    destinations = await ListDestinations(FakeOffers(pairs))()
    assert destinations == [("Portugal", "Lisbon"), ("Portugal", "Porto")]


async def test_covered_destinations_are_unique_and_sorted():
    a = _partner(country="Morocco", city="Marrakech")
    b = _partner(country="Greece", city="Chania")
    c = _partner(country="Morocco", city="Marrakech")
    pairs = [(_offer(a), a), (_offer(b), b), (_offer(c), c)]
    destinations = await ListDestinations(FakeOffers(pairs))()
    assert destinations == [("Greece", "Chania"), ("Morocco", "Marrakech")]


async def test_tags_at_returns_listed_offer_tags():
    hotel = _partner(country="Greece", city="Chania")
    stay = _offer(hotel, tags=("style:beach", "rhythm:calm"))
    walk = _offer(hotel, kind=OfferKind.GUIDE, tags=("style:culture", "food:local"))
    tags = await ListTagsAt(FakeOffers([(stay, hotel), (walk, hotel)]))("Greece", "Chania")
    assert tags == ["food:local", "rhythm:calm", "style:beach", "style:culture"]


async def test_tags_at_hides_inactive_partner_and_inactive_offer():
    open_hotel = _partner(country="Morocco", city="Marrakech", active=True)
    closed_agency = _partner(country="Morocco", city="Marrakech", active=False)
    riad = _offer(open_hotel, tags=("accommodation:riad", "style:culture"))
    desk = _offer(closed_agency, tags=("style:package",))
    inactive = _offer(open_hotel, active=False, tags=("style:hidden",))
    listed = [(riad, open_hotel), (desk, closed_agency), (inactive, open_hotel)]
    tags = await ListTagsAt(FakeOffers(listed))("Morocco", "Marrakech")
    assert tags == ["accommodation:riad", "style:culture"]
    assert "style:package" not in tags
    assert "style:hidden" not in tags


async def test_tags_at_city_none_covers_the_whole_country():
    lisbon = _partner(country="Portugal", city="Lisbon")
    porto = _partner(country="Portugal", city="Porto")
    stay = _offer(lisbon, tags=("style:culture",))
    surf = _offer(porto, tags=("style:beach",))
    tags = await ListTagsAt(FakeOffers([(stay, lisbon), (surf, porto)]))("Portugal", None)
    assert tags == ["style:beach", "style:culture"]


async def test_tags_at_matches_country_and_city_ignoring_case():
    hotel = _partner(country="Greece", city="Chania")
    stay = _offer(hotel, tags=("style:beach",))
    tags = await ListTagsAt(FakeOffers([(stay, hotel)]))("greece", "chania")
    assert tags == ["style:beach"]


def test_public_module_exposes_the_two_functions_wishes_needs():
    assert inspect.iscoroutinefunction(covered_destinations)
    assert inspect.iscoroutinefunction(tags_at)
    assert list(inspect.signature(covered_destinations).parameters) == ["session"]
    assert list(inspect.signature(tags_at).parameters) == ["country", "city", "session"]
    annotations = inspect.signature(tags_at).parameters
    assert annotations["city"].annotation == (str | None)


# A caller's session


def test_public_functions_take_an_optional_keyword_only_session():
    for function in (covered_destinations, tags_at, public.search_offers, public.get_offers):
        parameter = inspect.signature(function).parameters["session"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is None


@pytest.fixture
def seen_sessions(monkeypatch) -> list[object]:
    """Repositories built by catalog.public record their session; opening one fails the test."""
    hotel = _partner(country="Greece", city="Chania")
    pairs = [(_offer(hotel, tags=("style:beach",)), hotel)]
    sessions: list[object] = []

    def repository(session: object) -> FakeOffers:
        sessions.append(session)
        return FakeOffers(pairs)

    def no_sessionmaker():
        raise AssertionError("catalog.public opened its own session")

    monkeypatch.setattr(public, "SqlOfferRepository", repository)
    monkeypatch.setattr(public, "get_sessionmaker", no_sessionmaker)
    return sessions


async def test_covered_destinations_with_a_session_reads_through_it(seen_sessions):
    caller_session = object()

    destinations = await covered_destinations(session=caller_session)

    assert destinations == [("Greece", "Chania")]
    assert seen_sessions == [caller_session]


async def test_tags_at_with_a_session_reads_through_it(seen_sessions):
    caller_session = object()

    tags = await tags_at("Greece", "Chania", session=caller_session)

    assert tags == ["style:beach"]
    assert seen_sessions == [caller_session]


async def test_search_offers_with_a_session_reads_through_it(seen_sessions):
    caller_session = object()

    offers = await public.search_offers(
        "Greece", "Chania", [], 2, date(2026, 5, 10), date(2026, 5, 17), session=caller_session
    )

    assert [offer.city for offer in offers] == ["Chania"]
    assert seen_sessions == [caller_session]


async def test_limits_at_with_a_session_reads_through_it(seen_sessions):
    caller_session = object()

    limits = await public.limits_at("Greece", "Chania", date(2026, 5, 15), session=caller_session)

    assert limits is not None
    assert (limits.persons_min, limits.persons_max) == (2, 4)
    assert (limits.first_date, limits.last_date) == (date(2026, 5, 15), SEASON_END)
    assert limits.open_months == (5, 6, 7, 8, 9, 10)
    assert seen_sessions == [caller_session]


async def test_limits_at_a_destination_without_offers_is_none(seen_sessions):
    assert await public.limits_at("Spain", "Seville", date(2026, 5, 15), session=object()) is None


def test_limits_at_takes_an_optional_keyword_only_session():
    parameter = inspect.signature(public.limits_at).parameters["session"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None


async def test_get_offers_keeps_order_and_inactive_rows():
    hotel = _partner()
    first = _offer(hotel, title="First")
    hidden = _offer(hotel, title="Hidden", active=False)
    skip = uuid4()
    found = await GetOffers(FakeOffers([(first, hotel), (hidden, hotel)]))(
        [hidden.id, skip, first.id]
    )
    assert [offer.title for offer in found] == ["Hidden", "First"]


@pytest.mark.parametrize(
    ("name", "country"),
    [
        ("Grèce", "Greece"),
        ("greece", "Greece"),
        ("  GRÈCE ", "Greece"),
        ("Corée du Sud", "South Korea"),
        # Any country, not only the DÉTOUR ones, and without accents as people type them.
        ("Allemagne", "Germany"),
        ("germany", "Germany"),
        ("Bresil", "Brazil"),
        ("Grece", "Greece"),
        ("Cote d'Ivoire", "Ivory Coast"),
    ],
)
def test_canonical_country_reads_french_and_english_names(name, country):
    assert public.canonical_country(name) == country


def test_canonical_country_of_an_unknown_name_is_none():
    assert public.canonical_country("Atlantide") is None
