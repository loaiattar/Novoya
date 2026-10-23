from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status

from novoya_api.accounts.public import require_admin
from novoya_api.planning.application.ports.plan_repository import QUEUE_CAP, QUEUE_PAGE
from novoya_api.planning.application.use_cases.get_admin_plan import GetAdminPlan
from novoya_api.planning.application.use_cases.get_agent_plan import GetAgentPlan
from novoya_api.planning.application.use_cases.get_plan import GetPlan
from novoya_api.planning.application.use_cases.list_admin_plans import ListAdminPlans
from novoya_api.planning.application.use_cases.list_quote_queue import ListQuoteQueue
from novoya_api.planning.application.use_cases.plan_offers import (
    AddItemCommand,
    AddPlanItem,
    ListPlanOffers,
)
from novoya_api.planning.application.use_cases.request_quote import RequestQuote
from novoya_api.planning.application.use_cases.set_extra_price import (
    SetExtraCommand,
    SetExtraPrice,
)
from novoya_api.planning.application.use_cases.set_item_price import SetItemCommand, SetItemPrice
from novoya_api.planning.application.use_cases.take_plan import TakePlan
from novoya_api.planning.domain.plan import PlanStatus
from novoya_api.planning.presentation.http.dependencies import (
    get_add_plan_item,
    get_answer_days,
    get_current_agent_id,
    get_current_user_id,
    get_get_admin_plan,
    get_get_agent_plan,
    get_get_plan,
    get_list_admin_plans,
    get_list_plan_offers,
    get_list_quote_queue,
    get_request_quote,
    get_set_extra_price,
    get_set_item_price,
    get_take_plan,
)
from novoya_api.planning.presentation.http.schemas import (
    AddPlanItemRequest,
    AdminPlan,
    AdminPlanEntry,
    AgentOffer,
    AgentPlan,
    Plan,
    QueueEntry,
    RequestQuoteRequest,
    SetPlanExtraRequest,
    SetPlanItemRequest,
)
from novoya_api.shared.presentation.http.errors import ErrorResponse

ERRORS = {status_code: {"model": ErrorResponse} for status_code in (401, 403, 404)}

router = APIRouter(prefix="/plans", tags=["planning"], responses=ERRORS)


@router.get("/{plan_id}", operation_id="getPlan")
async def get_plan(
    plan_id: UUID,
    reader_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[GetPlan, Depends(get_get_plan)],
    answer_days: Annotated[int, Depends(get_answer_days)],
) -> Plan:
    """The plan day by day. Never a price: the quote has it. Never the partners' names.
    404 if it is missing or not the caller's, so the id stays hidden."""
    return Plan.of(await use_case(plan_id, reader_id), answer_days)


@router.post(
    "/{plan_id}/request-quote",
    operation_id="requestQuote",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def request_quote(
    plan_id: UUID,
    client_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[RequestQuote, Depends(get_request_quote)],
    answer_days: Annotated[int, Depends(get_answer_days)],
    body: Annotated[RequestQuoteRequest | None, Body()] = None,
) -> Plan:
    """Send this plan to the agency, with optional extras: proposed becomes requested, and the
    client gets one email saying the agency will answer within answer_within_days days. Never
    a price here. 404 if it is missing or not the caller's. 409 if it is not proposed (a second
    click too: no second request, no second email). 422 if an extra is unknown or no longer
    offered. A failed email does not fail the request."""
    extra_ids = body.extra_ids if body is not None else []
    return Plan.of(await use_case(plan_id, client_id, extra_ids), answer_days)


QueueStatus = Literal["requested", "negotiating", "quoted", "accepted", "rejected"]

agent_router = APIRouter(
    prefix="/agent/plans",
    tags=["agent"],
    responses=ERRORS,
)


@agent_router.get("", operation_id="listQuoteQueue")
async def list_quote_queue(
    use_case: Annotated[ListQuoteQueue, Depends(get_list_quote_queue)],
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    status: Annotated[list[QueueStatus], Query()] = ["requested"],  # noqa: B006
    limit: Annotated[int, Query(ge=1, le=QUEUE_CAP)] = QUEUE_PAGE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[QueueEntry]:
    """The agent's queue, oldest first. Wish text, destination, dates, travellers, budget.
    status repeats: requested lists the plans waiting for anyone; negotiating, quoted,
    accepted and rejected list only the caller's own plans. Never a price and never a
    partner name: open the plan to see those."""
    statuses = [PlanStatus(value) for value in dict.fromkeys(status)]
    return [
        QueueEntry.of(entry)
        for entry in await use_case(agent_id, statuses, limit=limit, offset=offset)
    ]


@agent_router.get("/{plan_id}", operation_id="getAgentPlan")
async def get_agent_plan(
    plan_id: UUID,
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    use_case: Annotated[GetAgentPlan, Depends(get_get_agent_plan)],
) -> AgentPlan:
    """The plan as the assigned agent sees it: prices, partners to call, total vs budget.
    403 if another agent took it."""
    return AgentPlan.of(await use_case(plan_id, agent_id))


@agent_router.post(
    "/{plan_id}/take",
    operation_id="takePlan",
    responses={409: {"model": ErrorResponse}},
)
async def take_plan(
    plan_id: UUID,
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    use_case: Annotated[TakePlan, Depends(get_take_plan)],
) -> AgentPlan:
    """Assign this requested plan to me and move it to negotiating. 409 if it is already taken."""
    return AgentPlan.of(await use_case(plan_id, agent_id))


@agent_router.get("/{plan_id}/offers", operation_id="listPlanOffers")
async def list_plan_offers(
    plan_id: UUID,
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    use_case: Annotated[ListPlanOffers, Depends(get_list_plan_offers)],
) -> list[AgentOffer]:
    """The offers the assigned agent may add to this plan: listed, taking the trip's
    travellers, open on at least one of its days, best first, with their open days and
    partner. 403 if another agent took the plan."""
    return [AgentOffer.of(offer) for offer in await use_case(plan_id, agent_id)]


@agent_router.post(
    "/{plan_id}/items",
    operation_id="addPlanItem",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def add_plan_item(
    plan_id: UUID,
    body: AddPlanItemRequest,
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    use_case: Annotated[AddPlanItem, Depends(get_add_plan_item)],
) -> AgentPlan:
    """Add an offer to the plan, with no price yet: how a custom request is built (#184).
    Only the assigned agent (403). 409 if the plan is no longer negotiating. 422 invalid_plan
    if the offer does not take the travellers, or is closed on the item's days."""
    return AgentPlan.of(
        await use_case(
            AddItemCommand(
                plan_id=plan_id,
                agent_id=agent_id,
                offer_id=body.offer_id,
                day=body.day,
                quantity=body.quantity,
                note=(body.note.strip() or None) if body.note else None,
            )
        )
    )


@agent_router.patch(
    "/{plan_id}/items/{item_id}",
    operation_id="setPlanItem",
    responses={409: {"model": ErrorResponse}},
)
async def set_plan_item(
    plan_id: UUID,
    item_id: UUID,
    body: SetPlanItemRequest,
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    use_case: Annotated[SetItemPrice, Depends(get_set_item_price)],
) -> AgentPlan:
    """Set the negotiated price in EUR, or set removed (true drops, false puts back).
    Only the assigned agent. 409 if the plan is no longer negotiating."""
    return AgentPlan.of(
        await use_case(
            SetItemCommand(
                plan_id=plan_id,
                item_id=item_id,
                agent_id=agent_id,
                negotiated_price=body.negotiated_price,
                removed=body.removed,
            )
        )
    )


@agent_router.patch(
    "/{plan_id}/extras/{extra_id}",
    operation_id="setPlanExtra",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def set_plan_extra(
    plan_id: UUID,
    extra_id: UUID,
    body: SetPlanExtraRequest,
    agent_id: Annotated[UUID, Depends(get_current_agent_id)],
    use_case: Annotated[SetExtraPrice, Depends(get_set_extra_price)],
) -> AgentPlan:
    """Set the price in EUR of an on_quote extra, or adjust a supplement. Only the assigned
    agent. 404 if the extra is not on the plan. 409 if the plan is no longer negotiating."""
    return AgentPlan.of(
        await use_case(
            SetExtraCommand(
                plan_id=plan_id, extra_id=extra_id, agent_id=agent_id, price_eur=body.price_eur
            )
        )
    )


admin_router = APIRouter(
    prefix="/admin/plans",
    tags=["admin"],
    responses=ERRORS,
    dependencies=[Depends(require_admin)],
)


@admin_router.get("", operation_id="listAdminPlans")
async def list_admin_plans(
    use_case: Annotated[ListAdminPlans, Depends(get_list_admin_plans)],
    status: PlanStatus | None = None,
    q: Annotated[
        str | None,
        Query(max_length=254, description="Part of the client's email or name, or of the place"),
    ] = None,
    wish_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=QUEUE_CAP)] = QUEUE_PAGE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminPlanEntry]:
    """Every client's plans, last changed first: client, destination, dates, status and agent.
    No prices and no partner names: open the plan for those. Admin only."""
    entries = await use_case(status, q, wish_id, limit=limit, offset=offset)
    return [AdminPlanEntry.of(entry) for entry in entries]


@admin_router.get("/{plan_id}", operation_id="getAdminPlan")
async def get_admin_plan(
    plan_id: UUID,
    use_case: Annotated[GetAdminPlan, Depends(get_get_admin_plan)],
) -> AdminPlan:
    """One plan, read-only: what its agent sees (prices, partners, total and budget), with the
    client and the agent. Admin only."""
    return AdminPlan.of(await use_case(plan_id))
