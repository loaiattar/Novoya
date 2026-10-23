from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from novoya_api.catalog.application.dto import ImportCounts
from novoya_api.catalog.application.use_cases.update_offer import CLEARABLE
from novoya_api.catalog.domain import Extra, Offer, Partner, Review

KindName = Literal["hotel", "guide", "transport", "activity", "agency"]
PriceUnitName = Literal["person/night", "person/trip", "person/activity"]
ExtraPricingName = Literal["included", "supplement", "on_quote"]
Month = Annotated[int, Field(ge=1, le=12)]
# Bounded so a value always fits the offers columns (int4), with room to spare.
PRICE_MAX_EUR = 1_000_000
DELAY_MAX_HOURS = 720  # 30 days
PERSONS_MAX = 1_000
Price = Annotated[int, Field(gt=0, le=PRICE_MAX_EUR)]
Delay = Annotated[int, Field(ge=0, le=DELAY_MAX_HOURS)]
Persons = Annotated[int, Field(ge=1, le=PERSONS_MAX)]
PlaceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
EmailText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]


class PartnerResponse(BaseModel):
    """A partner. imported: it comes from DÉTOUR, which owns everything but hidden (its offers
    too, but for featured and hidden): a PATCH of anything else is a 409 imported_row."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    kind: KindName
    country: str
    city: str
    contact_email: str
    contact_phone: str | None
    active: bool
    hidden: bool
    imported: bool

    @classmethod
    def of(cls, partner: Partner) -> "PartnerResponse":
        return cls(
            id=partner.id,
            name=partner.name,
            kind=partner.kind.value,
            country=partner.country,
            city=partner.city,
            contact_email=partner.contact_email,
            contact_phone=partner.contact_phone,
            active=partner.active,
            hidden=partner.hidden,
            imported=partner.imported,
        )


class CreatePartnerRequest(BaseModel):
    name: ShortText
    kind: KindName
    country: PlaceName
    city: PlaceName
    contact_email: EmailText
    contact_phone: Phone | None = None
    active: bool = True


class UpdatePartnerRequest(BaseModel):
    """Absent or null fields are unchanged. hidden hides the partner and its offers in Novoya;
    the DÉTOUR import never changes it. An imported partner only accepts hidden."""

    model_config = ConfigDict(extra="forbid")

    name: ShortText | None = None
    kind: KindName | None = None
    country: PlaceName | None = None
    city: PlaceName | None = None
    contact_email: EmailText | None = None
    contact_phone: Phone | None = None
    active: bool | None = None
    hidden: bool | None = None


class OfferResponse(BaseModel):
    """An offer, for agents. hidden: the agent's switch in Novoya, kept by the import."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    partner_id: UUID
    kind: KindName
    title: str
    description: str
    country: str
    city: str
    min_persons: int
    max_persons: int
    available_from: date
    available_to: date
    tags: list[str]
    featured: bool
    active: bool
    price_eur: int | None
    price_unit: PriceUnitName | None
    opening_months: list[int]
    conditions: str | None
    restrictions: str | None
    cancellation: str | None
    confirmation_delay_hours: int | None
    hidden: bool

    @classmethod
    def of(cls, offer: Offer) -> "OfferResponse":
        return cls(
            id=offer.id,
            partner_id=offer.partner_id,
            kind=offer.kind.value,
            title=offer.title,
            description=offer.description,
            country=offer.country,
            city=offer.city,
            min_persons=offer.min_persons,
            max_persons=offer.max_persons,
            available_from=offer.available_from,
            available_to=offer.available_to,
            tags=list(offer.tags),
            featured=offer.featured,
            active=offer.active,
            price_eur=offer.price_eur,
            price_unit=offer.price_unit.value if offer.price_unit is not None else None,
            opening_months=list(offer.opening_months),
            conditions=offer.conditions,
            restrictions=offer.restrictions,
            cancellation=offer.cancellation,
            confirmation_delay_hours=offer.confirmation_delay_hours,
            hidden=offer.hidden,
        )


class CreateOfferRequest(BaseModel):
    partner_id: UUID
    kind: KindName
    title: ShortText
    description: LongText
    country: PlaceName
    city: PlaceName
    min_persons: Persons
    max_persons: Persons
    available_from: date
    available_to: date
    tags: list[str] = Field(default_factory=list, max_length=50)
    featured: bool = False
    active: bool = True
    price_eur: Price | None = None
    price_unit: PriceUnitName | None = None
    opening_months: list[Month] = Field(default_factory=list, max_length=12)
    conditions: str | None = None
    restrictions: str | None = None
    cancellation: str | None = None
    confirmation_delay_hours: Delay | None = None


class UpdateOfferRequest(BaseModel):
    """Absent fields are unchanged, and so is null, except for price_eur and price_unit
    (cleared together) and opening_months (cleared to none). An offer of an imported partner
    only accepts featured and hidden: any other change is a 409 imported_row."""

    model_config = ConfigDict(extra="forbid")

    kind: KindName | None = None
    title: ShortText | None = None
    description: LongText | None = None
    country: PlaceName | None = None
    city: PlaceName | None = None
    min_persons: Persons | None = None
    max_persons: Persons | None = None
    available_from: date | None = None
    available_to: date | None = None
    tags: Annotated[list[str], Field(max_length=50)] | None = None
    featured: bool | None = None
    active: bool | None = None
    price_eur: Price | None = None
    price_unit: PriceUnitName | None = None
    opening_months: Annotated[list[Month], Field(max_length=12)] | None = None
    conditions: str | None = None
    restrictions: str | None = None
    cancellation: str | None = None
    confirmation_delay_hours: Delay | None = None
    hidden: bool | None = None

    def cleared(self) -> frozenset[str]:
        """The fields sent as an explicit null that null clears."""
        return frozenset(
            name
            for name in CLEARABLE
            if name in self.model_fields_set and getattr(self, name) is None
        )


class DestinationResponse(BaseModel):
    """A place Novoya can plan a trip, from listed partner offers."""

    model_config = ConfigDict(frozen=True)

    country: str
    city: str


class FeaturedOfferResponse(BaseModel):
    """A featured offer as a public inspiration card: no price, terms or partner."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    kind: KindName
    title: str
    description: str
    country: str
    city: str

    @classmethod
    def of(cls, offer: Offer) -> "FeaturedOfferResponse":
        return cls(
            id=offer.id,
            kind=offer.kind.value,
            title=offer.title,
            description=offer.description,
            country=offer.country,
            city=offer.city,
        )


class OfferDetailResponse(BaseModel):
    """A listed offer for its page. The price is indicative, per person (ADR 0014): the agent
    negotiates the price of the trip and the quote has it. Never the partner."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    kind: KindName
    title: str
    description: str
    country: str
    city: str
    min_persons: int
    max_persons: int
    available_from: date
    available_to: date
    tags: list[str]
    price_eur: int | None
    price_unit: PriceUnitName | None
    opening_months: list[int]
    conditions: str | None
    restrictions: str | None
    cancellation: str | None
    confirmation_delay_hours: int | None

    @classmethod
    def of(cls, offer: Offer) -> "OfferDetailResponse":
        return cls(
            id=offer.id,
            kind=offer.kind.value,
            title=offer.title,
            description=offer.description,
            country=offer.country,
            city=offer.city,
            min_persons=offer.min_persons,
            max_persons=offer.max_persons,
            available_from=offer.available_from,
            available_to=offer.available_to,
            tags=list(offer.tags),
            price_eur=offer.price_eur,
            price_unit=offer.price_unit.value if offer.price_unit is not None else None,
            opening_months=list(offer.opening_months),
            conditions=offer.conditions,
            restrictions=offer.restrictions,
            cancellation=offer.cancellation,
            confirmation_delay_hours=offer.confirmation_delay_hours,
        )


class ReviewResponse(BaseModel):
    """A published review. The author is "First name I." or "Voyageur anonyme", as given."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    country: str
    city: str
    rating: int
    reviewed_on: date
    text: str
    author: str

    @classmethod
    def of(cls, review: Review) -> "ReviewResponse":
        return cls.model_validate(review, from_attributes=True)


class AdminReviewResponse(ReviewResponse):
    """A review for admins: hidden ones too. hidden is the only field an admin changes;
    DÉTOUR owns the rest."""

    hidden: bool

    @classmethod
    def of(cls, review: Review) -> "AdminReviewResponse":
        return cls(**ReviewResponse.of(review).model_dump(), hidden=review.hidden)


class UpdateReviewRequest(BaseModel):
    """true hides the review from GET /reviews, false shows it again. The import never
    changes it."""

    model_config = ConfigDict(extra="forbid")

    hidden: bool


class ExtraResponse(BaseModel):
    """An option a client can add to a plan. supplement_eur only for a supplement."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    category: str
    label: str
    description: str
    pricing: ExtraPricingName
    supplement_eur: int | None
    unit: str
    constraints: list[str]

    @classmethod
    def of(cls, extra: Extra) -> "ExtraResponse":
        return cls(
            id=extra.id,
            category=extra.category,
            label=extra.label,
            description=extra.description,
            pricing=extra.pricing.value,
            supplement_eur=extra.supplement_eur,
            unit=extra.unit,
            constraints=list(extra.constraints),
        )


class AdminExtraResponse(ExtraResponse):
    """An extra, for agents: inactive ones (gone from the DÉTOUR export) and hidden ones too.
    hidden is the only field an agent changes; DÉTOUR owns the rest."""

    active: bool
    hidden: bool

    @classmethod
    def of(cls, extra: Extra) -> "AdminExtraResponse":
        return cls(**ExtraResponse.of(extra).model_dump(), active=extra.active, hidden=extra.hidden)


class UpdateExtraRequest(BaseModel):
    """true hides the extra from clients, false shows it again. The import never changes it."""

    model_config = ConfigDict(extra="forbid")

    hidden: bool


class ImportLimitsResponse(BaseModel):
    """What the import accepts, so the page refuses a file before sending it."""

    max_bytes: int


class ImportCountsResponse(BaseModel):
    """What the DÉTOUR import wrote: rows in the export, imported or updated."""

    partners: int
    offers: int
    reviews: int
    extras: int

    @classmethod
    def of(cls, counts: ImportCounts) -> "ImportCountsResponse":
        return cls(
            partners=counts.partners,
            offers=counts.offers,
            reviews=counts.reviews,
            extras=counts.extras,
        )
