"""Fixed catalog so every developer has the same partners and offers."""

from datetime import date
from uuid import UUID

from novoya_api.catalog.domain.kinds import OfferKind, PartnerKind

# Crete
P_CRETE_HOTEL = UUID("11111111-1111-4111-8111-111111111111")
P_CRETE_GUIDE = UUID("11111111-1111-4111-8111-111111111112")
# Basque coast
P_BASQUE_TRANSPORT = UUID("22222222-2222-4222-8222-222222222221")
P_BASQUE_ACTIVITY = UUID("22222222-2222-4222-8222-222222222222")
# Marrakech
P_MARRAKECH_HOTEL = UUID("33333333-3333-4333-8333-333333333331")
P_MARRAKECH_AGENCY = UUID("33333333-3333-4333-8333-333333333332")

O_CRETE_STAY = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
O_CRETE_WALK = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
O_BASQUE_TRANSFER = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1")
O_BASQUE_SURF = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2")
O_MARRAKECH_RIAD = UUID("cccccccc-cccc-4ccc-8ccc-ccccccccccc1")
O_MARRAKECH_DESK = UUID("cccccccc-cccc-4ccc-8ccc-ccccccccccc2")

# From the date the seed runs, so the season never ends under a developer: this year and next.
# Running the seed again refreshes the dates.
SEASON_START = date(date.today().year, 1, 1)
SEASON_END = date(date.today().year + 1, 12, 31)

PARTNERS: list[dict] = [
    {
        "id": P_CRETE_HOTEL,
        "name": "Elounda Bay House",
        "kind": PartnerKind.HOTEL,
        "country": "Greece",
        "city": "Chania",
        "contact_email": "stay@elounda.example",
        "contact_phone": "+30 28210 00001",
        "active": True,
    },
    {
        "id": P_CRETE_GUIDE,
        "name": "Cretan Paths",
        "kind": PartnerKind.GUIDE,
        "country": "Greece",
        "city": "Chania",
        "contact_email": "hello@cretanpaths.example",
        "contact_phone": "+30 28210 00002",
        "active": True,
    },
    {
        "id": P_BASQUE_TRANSPORT,
        "name": "Côte Basque Transfers",
        "kind": PartnerKind.TRANSPORT,
        "country": "France",
        "city": "Biarritz",
        "contact_email": "rides@basque-transfers.example",
        "contact_phone": "+33 5 59 00 00 01",
        "active": True,
    },
    {
        "id": P_BASQUE_ACTIVITY,
        "name": "Grande Plage Surf",
        "kind": PartnerKind.ACTIVITY,
        "country": "France",
        "city": "Biarritz",
        "contact_email": "waves@grandeplage.example",
        "contact_phone": "+33 5 59 00 00 02",
        "active": True,
    },
    {
        "id": P_MARRAKECH_HOTEL,
        "name": "Riad Atlas",
        "kind": PartnerKind.HOTEL,
        "country": "Morocco",
        "city": "Marrakech",
        "contact_email": "book@riadatlas.example",
        "contact_phone": "+212 524 00 00 01",
        "active": True,
    },
    {
        "id": P_MARRAKECH_AGENCY,
        "name": "Atlas Closed Desk",
        "kind": PartnerKind.AGENCY,
        "country": "Morocco",
        "city": "Marrakech",
        "contact_email": "desk@atlasclosed.example",
        "contact_phone": "+212 524 00 00 02",
        "active": False,
    },
]

OFFERS: list[dict] = [
    {
        "id": O_CRETE_STAY,
        "partner_id": P_CRETE_HOTEL,
        "kind": OfferKind.HOTEL,
        "title": "Sea-view room, Elounda",
        "description": "Calm week by the water, breakfast included.",
        "country": "Greece",
        "city": "Chania",
        "min_persons": 1,
        "max_persons": 3,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ["style:beach", "rhythm:calm", "style:sea"],
        "featured": True,
        "active": True,
    },
    {
        "id": O_CRETE_WALK,
        "partner_id": P_CRETE_GUIDE,
        "kind": OfferKind.GUIDE,
        "title": "Chania old town walk",
        "description": "Culture and food with a local guide.",
        "country": "Greece",
        "city": "Chania",
        "min_persons": 2,
        "max_persons": 8,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ["style:culture", "food:local", "style:walk"],
        "featured": False,
        "active": True,
    },
    {
        "id": O_BASQUE_TRANSFER,
        "partner_id": P_BASQUE_TRANSPORT,
        "kind": OfferKind.TRANSPORT,
        "title": "Biarritz airport transfer",
        "description": "Private car between the airport and the coast.",
        "country": "France",
        "city": "Biarritz",
        "min_persons": 1,
        "max_persons": 4,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ["transport:airport", "rhythm:easy"],
        "featured": False,
        "active": True,
    },
    {
        "id": O_BASQUE_SURF,
        "partner_id": P_BASQUE_ACTIVITY,
        "kind": OfferKind.ACTIVITY,
        "title": "Surf lesson on Grande Plage",
        "description": "Half-day group lesson, board included.",
        "country": "France",
        "city": "Biarritz",
        "min_persons": 1,
        "max_persons": 6,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ["style:beach", "style:sport", "style:sea"],
        "featured": True,
        "active": True,
    },
    {
        "id": O_MARRAKECH_RIAD,
        "partner_id": P_MARRAKECH_HOTEL,
        "kind": OfferKind.HOTEL,
        "title": "Riad room in the medina",
        "description": "Traditional courtyard house, two nights minimum.",
        "country": "Morocco",
        "city": "Marrakech",
        "min_persons": 2,
        "max_persons": 4,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ["style:culture", "rhythm:calm", "food:local", "accommodation:riad"],
        "featured": True,
        "active": True,
    },
    {
        "id": O_MARRAKECH_DESK,
        "partner_id": P_MARRAKECH_AGENCY,
        "kind": OfferKind.AGENCY,
        "title": "Desk-only package (inactive partner)",
        "description": "Must never be used while the partner is inactive.",
        "country": "Morocco",
        "city": "Marrakech",
        "min_persons": 2,
        "max_persons": 10,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ["style:package"],
        "featured": False,
        "active": True,
    },
]
