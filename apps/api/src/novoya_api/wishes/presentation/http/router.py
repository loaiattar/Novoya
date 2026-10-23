from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Response, status

from novoya_api.accounts.public import require_admin
from novoya_api.shared.domain.errors import InvalidInput
from novoya_api.shared.presentation.http.errors import ErrorResponse
from novoya_api.wishes.application.ports.wish_repository import ADMIN_CAP, ADMIN_PAGE
from novoya_api.wishes.application.use_cases.answer_panel import AnswerPanel, AnswerPanelCommand
from novoya_api.wishes.application.use_cases.closest_dates import GetClosestDates
from novoya_api.wishes.application.use_cases.get_panel_limits import GetPanelLimits
from novoya_api.wishes.application.use_cases.list_admin_wishes import ListAdminWishes
from novoya_api.wishes.application.use_cases.preferences import ListPreferences, RemovePreference
from novoya_api.wishes.application.use_cases.send_custom_request import SendCustomRequest
from novoya_api.wishes.application.use_cases.send_wish import SendWish, SendWishCommand
from novoya_api.wishes.domain.wish import WishStatus
from novoya_api.wishes.presentation.http.dependencies import (
    get_answer_panel,
    get_closest_dates,
    get_current_user_id,
    get_list_admin_wishes,
    get_list_preferences,
    get_panel_limits,
    get_remove_preference,
    get_send_custom_request,
    get_send_wish,
)
from novoya_api.wishes.presentation.http.schemas import (
    AdminWish,
    AnswerPanelRequest,
    CustomRequestResponse,
    DateOptionOut,
    PanelLimitsOut,
    PlanResponse,
    PreferenceSectionOut,
    SendWishRequest,
    WishResponse,
    WishStatusName,
)

# Every error body is {code, detail} (shared handler), not FastAPI's default 422 list.
# 429: each client sends a limited number of wishes and answers per hour (they call the model).
ERRORS = {status_code: {"model": ErrorResponse} for status_code in (401, 403, 422, 429)}

router = APIRouter(prefix="/wishes", tags=["wishes"], responses=ERRORS)


@router.post("", operation_id="sendWish", status_code=status.HTTP_201_CREATED)
async def send_wish(
    body: SendWishRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[SendWish, Depends(get_send_wish)],
) -> WishResponse:
    """Send the trip the client wants, in their words. Returns the panel when we cover the
    destination, suggestions when we don't, and asks where when the text names no place."""
    return WishResponse.of(await use_case(SendWishCommand(user_id=user_id, text=body.text)))


@router.post(
    "/{wish_id}/answers",
    operation_id="answerPanel",
    status_code=status.HTTP_201_CREATED,
    responses={status_code: {"model": ErrorResponse} for status_code in (404, 409)},
)
async def answer_panel(
    wish_id: UUID,
    body: AnswerPanelRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[AnswerPanel, Depends(get_answer_panel)],
) -> PlanResponse:
    """Save the tags the client picked, their budget in EUR, travellers and dates, and return
    the proposed plan built from partner offers. 404 if the wish is not theirs; 409 if it is
    already answered, shows no panel or is being answered by another request; 422 for a tag
    the panel did not show, and 422 no_offer_fits when no offer fits the travellers and
    dates."""
    command = AnswerPanelCommand(user_id=user_id, wish_id=wish_id, answers=body.to_answers())
    return PlanResponse.of((await use_case(command)).plan)


@router.get(
    "/{wish_id}/limits",
    operation_id="getPanelLimits",
    responses={404: {"model": ErrorResponse}},
)
async def get_limits(
    wish_id: UUID,
    response: Response,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[GetPanelLimits, Depends(get_panel_limits)],
    persons: Annotated[int | None, Query(ge=1, le=50)] = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> PanelLimitsOut:
    """What the panel of this wish may offer, from the destination's listed offers today
    (#183): travellers (at most 50), first and last open days, months with an open offer.
    With persons, start_date and end_date (all three or none), also whether a plan can be
    built for them, by the plan's own rule, and the limits of the offers taking that group.
    422 invalid_answers for dates the answer would refuse (end not after start, departure in
    the past, over 366 days). 404 if the wish is not theirs or has no destination yet. 429
    past the client's limit of reads."""
    given = [value is not None for value in (persons, start_date, end_date)]
    if any(given) and not all(given):
        raise InvalidInput("give persons, start_date and end_date together, or none")
    view = await use_case(wish_id, user_id, persons, start_date, end_date)
    # The catalog changes at any time, and the limits are the client's own trip.
    response.headers["Cache-Control"] = PRIVATE
    return PanelLimitsOut.of(view)


@router.post(
    "/{wish_id}/custom-request",
    operation_id="sendCustomRequest",
    status_code=status.HTTP_201_CREATED,
    responses={status_code: {"model": ErrorResponse} for status_code in (404, 409)},
)
async def send_custom_request(
    wish_id: UUID,
    body: AnswerPanelRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[SendCustomRequest, Depends(get_send_custom_request)],
) -> CustomRequestResponse:
    """Send the panel answers to the agency as they are, when no offer fits them (#184): the
    wish's plan is a custom request, requested at once, with no item, and an advisor builds
    it. The client gets the same email as for a plan sent to the agency. The same body and
    rules as the answer: 404 if the wish is not theirs; 409 if it is already answered (a
    second click too: no second request) or being answered by another request; 422 for a tag
    the panel did not show or dates it refuses; 429 past the limit of answers."""
    command = AnswerPanelCommand(user_id=user_id, wish_id=wish_id, answers=body.to_answers())
    return CustomRequestResponse.of((await use_case(command)).plan)


@router.get(
    "/{wish_id}/closest-dates",
    operation_id="getClosestDates",
    responses={404: {"model": ErrorResponse}},
)
async def get_closest_dates(
    wish_id: UUID,
    response: Response,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[GetClosestDates, Depends(get_closest_dates)],
    persons: Annotated[int, Query(ge=1, le=50)],
    start_date: date,
    end_date: date,
) -> list[DateOptionOut]:
    """When no offer fits these travellers and dates (#184), the nearest dates before and
    after, the same length and group, for which a plan can be built, by the plan's own rule,
    with how many offers fit then. At most two, none before today; empty when none is within
    90 days. 422 invalid_answers for dates the answer would refuse. 404 if the wish is not
    theirs or has no destination yet. 429 past the client's limit of reads."""
    options = await use_case(wish_id, user_id, persons, start_date, end_date)
    response.headers["Cache-Control"] = PRIVATE
    return [DateOptionOut.of(option) for option in options]


# The client's own tastes: no shared or browser cache keeps them.
PRIVATE = "private, no-store"
# No max length: a tag from an import can be long, and the lookup is equality on the
# client's own wishes.
TagId = Annotated[str, Path(min_length=1)]

me_router = APIRouter(
    prefix="/me/preferences",
    tags=["me"],
    responses={status_code: {"model": ErrorResponse} for status_code in (401, 403, 422)},
)


@me_router.get("", operation_id="listMyPreferences")
async def list_my_preferences(
    response: Response,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[ListPreferences, Depends(get_list_preferences)],
) -> list[PreferenceSectionOut]:
    """The tags the client picked on the panels of their own wishes, grouped by panel
    section, each tag once, with whether it can still be removed. Empty when no wish is
    answered yet."""
    response.headers["Cache-Control"] = PRIVATE
    return [PreferenceSectionOut.of(section) for section in await use_case(user_id)]


@me_router.delete(
    "/{section}/{tag}",
    operation_id="removeMyPreference",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"model": ErrorResponse}},
)
async def remove_my_preference(
    section: TagId,
    tag: TagId,
    response: Response,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[RemovePreference, Depends(get_remove_preference)],
) -> None:
    """Withdraw a preference from the client's wishes that can still change: those with no
    plan requested, negotiating, quoted, accepted or rejected. Wishes the agency works from keep it.
    409 preference_locked when every wish carrying the tag is with the agency. Removing a tag
    the client does not have is a no-op (204), so a second click does no harm."""
    response.headers["Cache-Control"] = PRIVATE
    await use_case(user_id, section, tag)


admin_router = APIRouter(
    prefix="/admin/wishes",
    tags=["admin"],
    responses={status_code: {"model": ErrorResponse} for status_code in (401, 403)},
    dependencies=[Depends(require_admin)],
)


@admin_router.get("", operation_id="listAdminWishes")
async def list_admin_wishes(
    use_case: Annotated[ListAdminWishes, Depends(get_list_admin_wishes)],
    status: WishStatusName | None = None,
    q: Annotated[
        str | None,
        Query(
            max_length=254,
            description="Part of the client's email or name, or of the country or city",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_CAP)] = ADMIN_PAGE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminWish]:
    """Every client's wishes, last changed first, with who sent them. Admin only."""
    wishes = await use_case(WishStatus(status) if status else None, q, limit=limit, offset=offset)
    return [AdminWish.of(wish) for wish in wishes]
