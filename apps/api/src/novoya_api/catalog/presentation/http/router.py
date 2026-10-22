from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from novoya_api.accounts.public import current_user, require_admin
from novoya_api.catalog.application.use_cases.create_offer import CreateOffer, CreateOfferCommand
from novoya_api.catalog.application.use_cases.create_partner import (
    CreatePartner,
    CreatePartnerCommand,
)
from novoya_api.catalog.application.use_cases.get_offer_detail import GetOfferDetail
from novoya_api.catalog.application.use_cases.list_all_extras import ListAllExtras
from novoya_api.catalog.application.use_cases.list_all_reviews import ListAllReviews
from novoya_api.catalog.application.use_cases.list_destinations import ListDestinations
from novoya_api.catalog.application.use_cases.list_extras import ListExtras
from novoya_api.catalog.application.use_cases.list_offers import ListOffers
from novoya_api.catalog.application.use_cases.list_partners import ListPartners
from novoya_api.catalog.application.use_cases.list_reviews import ListReviews
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
from novoya_api.catalog.domain import OfferKind, PartnerKind, PriceUnit
from novoya_api.catalog.presentation.http.dependencies import (
    get_create_offer,
    get_create_partner,
    get_get_offer_detail,
    get_list_all_extras,
    get_list_all_reviews,
    get_list_destinations,
    get_list_extras,
    get_list_offers,
    get_list_partners,
    get_list_reviews,
    get_update_extra,
    get_update_offer,
    get_update_partner,
    get_update_review,
)
from novoya_api.catalog.presentation.http.schemas import (
    AdminExtraResponse,
    AdminReviewResponse,
    CreateOfferRequest,
    CreatePartnerRequest,
    DestinationResponse,
    ExtraResponse,
    OfferDetailResponse,
    OfferResponse,
    PartnerResponse,
    PlaceName,
    ReviewResponse,
    UpdateExtraRequest,
    UpdateOfferRequest,
    UpdatePartnerRequest,
    UpdateReviewRequest,
)
from novoya_api.shared.presentation.http.errors import ErrorResponse

ERRORS = {status_code: {"model": ErrorResponse} for status_code in (401, 403, 404, 409, 422)}

destinations_router = APIRouter(tags=["catalog"])
signed_in_router = APIRouter(
    tags=["catalog"],
    responses={status_code: {"model": ErrorResponse} for status_code in (401, 404)},
    dependencies=[Depends(current_user)],
)
partners_router = APIRouter(
    prefix="/admin/partners",
    tags=["admin"],
    responses=ERRORS,
    dependencies=[Depends(require_admin)],
)
offers_router = APIRouter(
    prefix="/admin/offers",
    tags=["admin"],
    responses=ERRORS,
    dependencies=[Depends(require_admin)],
)

extras_router = APIRouter(
    prefix="/admin/extras",
    tags=["admin"],
    responses=ERRORS,
    dependencies=[Depends(require_admin)],
)
reviews_router = APIRouter(
    prefix="/admin/reviews",
    tags=["admin"],
    responses=ERRORS,
    dependencies=[Depends(require_admin)],
)


@destinations_router.get("/destinations", operation_id="listDestinations")
async def list_destinations(
    use_case: Annotated[ListDestinations, Depends(get_list_destinations)],
) -> list[DestinationResponse]:
    """Countries and cities with at least one listed offer. Read from the database each time."""
    return [DestinationResponse(country=country, city=city) for country, city in await use_case()]


@destinations_router.get("/reviews", operation_id="listReviews")
async def list_reviews(
    use_case: Annotated[ListReviews, Depends(get_list_reviews)],
    country: Annotated[PlaceName | None, Query()] = None,
    city: Annotated[PlaceName | None, Query()] = None,
) -> list[ReviewResponse]:
    """Published reviews, newest first, at most 100. Public: only reviews the travellers agreed
    to publish, under "First name I." or "Voyageur anonyme". Hidden reviews are omitted.
    Filter by country and city."""
    return [ReviewResponse.of(review) for review in await use_case(country, city)]


@signed_in_router.get("/offers/{offer_id}", operation_id="getOffer")
async def get_offer(
    offer_id: UUID,
    use_case: Annotated[GetOfferDetail, Depends(get_get_offer_detail)],
) -> OfferDetailResponse:
    """A listed offer: indicative price per person, opening months and terms. Never the partner.
    The agent still negotiates the trip's price. 404 if it is unknown or not listed."""
    return OfferDetailResponse.of(await use_case(offer_id))


@signed_in_router.get("/extras", operation_id="listExtras")
async def list_extras(
    use_case: Annotated[ListExtras, Depends(get_list_extras)],
) -> list[ExtraResponse]:
    """Options a client can add when asking for a quote. Active ones that no agent hid."""
    return [ExtraResponse.of(extra) for extra in await use_case()]


@partners_router.get("", operation_id="listPartners")
async def list_partners(
    use_case: Annotated[ListPartners, Depends(get_list_partners)],
) -> list[PartnerResponse]:
    """All partners, including inactive ones. Agents only."""
    return [PartnerResponse.of(partner) for partner in await use_case()]


@partners_router.post("", operation_id="createPartner", status_code=status.HTTP_201_CREATED)
async def create_partner(
    body: CreatePartnerRequest,
    use_case: Annotated[CreatePartner, Depends(get_create_partner)],
) -> PartnerResponse:
    """Add a partner. Agents only."""
    partner = await use_case(
        CreatePartnerCommand(
            name=body.name,
            kind=PartnerKind(body.kind),
            country=body.country,
            city=body.city,
            contact_email=body.contact_email,
            contact_phone=body.contact_phone,
            active=body.active,
        )
    )
    return PartnerResponse.of(partner)


@partners_router.patch("/{partner_id}", operation_id="updatePartner")
async def update_partner(
    partner_id: UUID,
    body: UpdatePartnerRequest,
    use_case: Annotated[UpdatePartner, Depends(get_update_partner)],
) -> PartnerResponse:
    """Change a partner. Deactivating or hiding it hides its offers from search. A partner
    imported from DÉTOUR only changes hidden: anything else is 409 imported_row. Agents only."""
    partner = await use_case(
        UpdatePartnerCommand(
            partner_id=partner_id,
            name=body.name,
            kind=PartnerKind(body.kind) if body.kind is not None else None,
            country=body.country,
            city=body.city,
            contact_email=body.contact_email,
            contact_phone=body.contact_phone,
            active=body.active,
            hidden=body.hidden,
        )
    )
    return PartnerResponse.of(partner)


@offers_router.get("", operation_id="listOffers")
async def list_offers(
    use_case: Annotated[ListOffers, Depends(get_list_offers)],
    partner_id: Annotated[UUID | None, Query()] = None,
) -> list[OfferResponse]:
    """All offers, including inactive ones. With partner_id, only that partner's offers (an
    unknown partner gives an empty list). Agents only."""
    return [OfferResponse.of(offer) for offer in await use_case(partner_id)]


@offers_router.post("", operation_id="createOffer", status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: CreateOfferRequest,
    use_case: Annotated[CreateOffer, Depends(get_create_offer)],
) -> OfferResponse:
    """Add an offer for an existing partner made in Novoya. A partner imported from DÉTOUR gets
    its offers from DÉTOUR: 409 imported_row. Agents only."""
    offer = await use_case(
        CreateOfferCommand(
            partner_id=body.partner_id,
            kind=OfferKind(body.kind),
            title=body.title,
            description=body.description,
            country=body.country,
            city=body.city,
            min_persons=body.min_persons,
            max_persons=body.max_persons,
            available_from=body.available_from,
            available_to=body.available_to,
            tags=tuple(body.tags),
            featured=body.featured,
            active=body.active,
            price_eur=body.price_eur,
            price_unit=PriceUnit(body.price_unit) if body.price_unit is not None else None,
            opening_months=tuple(body.opening_months),
            conditions=body.conditions,
            restrictions=body.restrictions,
            cancellation=body.cancellation,
            confirmation_delay_hours=body.confirmation_delay_hours,
        )
    )
    return OfferResponse.of(offer)


@offers_router.patch("/{offer_id}", operation_id="updateOffer")
async def update_offer(
    offer_id: UUID,
    body: UpdateOfferRequest,
    use_case: Annotated[UpdateOffer, Depends(get_update_offer)],
) -> OfferResponse:
    """Change an offer. null clears the price with its unit, or the opening months. An offer of
    a partner imported from DÉTOUR only changes featured and hidden: anything else is 409
    imported_row. Agents only."""
    offer = await use_case(
        UpdateOfferCommand(
            offer_id=offer_id,
            kind=OfferKind(body.kind) if body.kind is not None else None,
            title=body.title,
            description=body.description,
            country=body.country,
            city=body.city,
            min_persons=body.min_persons,
            max_persons=body.max_persons,
            available_from=body.available_from,
            available_to=body.available_to,
            tags=tuple(body.tags) if body.tags is not None else None,
            featured=body.featured,
            active=body.active,
            price_eur=body.price_eur,
            price_unit=PriceUnit(body.price_unit) if body.price_unit is not None else None,
            opening_months=(
                tuple(body.opening_months) if body.opening_months is not None else None
            ),
            conditions=body.conditions,
            restrictions=body.restrictions,
            cancellation=body.cancellation,
            confirmation_delay_hours=body.confirmation_delay_hours,
            hidden=body.hidden,
            cleared=body.cleared(),
        )
    )
    return OfferResponse.of(offer)


@extras_router.get("", operation_id="listAllExtras")
async def list_all_extras(
    use_case: Annotated[ListAllExtras, Depends(get_list_all_extras)],
) -> list[AdminExtraResponse]:
    """All extras, inactive and hidden ones too. Agents only."""
    return [AdminExtraResponse.of(extra) for extra in await use_case()]


@extras_router.patch("/{extra_id}", operation_id="updateExtra")
async def update_extra(
    extra_id: UUID,
    body: UpdateExtraRequest,
    use_case: Annotated[UpdateExtra, Depends(get_update_extra)],
) -> AdminExtraResponse:
    """Hide an extra from clients, or show it again. Extras come from DÉTOUR, which owns the
    rest: the import never changes hidden. Agents only."""
    return AdminExtraResponse.of(await use_case(UpdateExtraCommand(extra_id, hidden=body.hidden)))


@reviews_router.get("", operation_id="listAllReviews")
async def list_all_reviews(
    use_case: Annotated[ListAllReviews, Depends(get_list_all_reviews)],
) -> list[AdminReviewResponse]:
    """All published reviews, hidden ones too, newest first. No paging: there are few
    enough. Admins only."""
    return [AdminReviewResponse.of(review) for review in await use_case()]


@reviews_router.patch("/{review_id}", operation_id="updateReview")
async def update_review(
    review_id: UUID,
    body: UpdateReviewRequest,
    use_case: Annotated[UpdateReview, Depends(get_update_review)],
) -> AdminReviewResponse:
    """Hide a review from GET /reviews, or show it again. The import never changes hidden.
    Admins only."""
    return AdminReviewResponse.of(
        await use_case(UpdateReviewCommand(review_id, hidden=body.hidden))
    )


router = APIRouter()
router.include_router(destinations_router)
router.include_router(signed_in_router)
router.include_router(partners_router)
router.include_router(offers_router)
router.include_router(extras_router)
router.include_router(reviews_router)
