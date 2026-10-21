from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query

from novoya_api.planning.application.ports.plan_repository import QUEUE_CAP, QUEUE_PAGE
from novoya_api.planning.application.use_cases.get_agent_plan import GetAgentPlan
from novoya_api.planning.application.use_cases.get_plan import GetPlan
from novoya_api.planning.application.use_cases.list_quote_queue import ListQuoteQueue
from novoya_api.planning.application.use_cases.request_quote import RequestQuote
from novoya_api.planning.application.use_cases.set_extra_price import (
    SetExtraCommand,
    SetExtraPrice,
)
from novoya_api.planning.application.use_cases.set_item_price import SetItemCommand, SetItemPrice
from novoya_api.planning.application.use_cases.take_plan import TakePlan
from novoya_api.planning.domain.plan import PlanStatus
from novoya_api.planning.presentation.http.dependencies import (
    get_current_agent_id,
    get_current_user_id,
    get_get_agent_plan,
    get_get_plan,
    get_list_quote_queue,
    get_request_quote,
    get_set_extra_price,
    get_set_item_price,
    get_take_plan,
)
from novoya_api.planning.presentation.http.schemas import (
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
) -> Plan:
    """The plan day by day. Never a price: the quote has it. Never the partners' names.
    404 if it is missing or not the caller's, so the id stays hidden."""
    return Plan.of(await use_case(plan_id, reader_id))


@router.post(
    "/{plan_id}/request-quote",
    operation_id="requestQuote",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def request_quote(
    plan_id: UUID,
    client_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[RequestQuote, Depends(get_request_quote)],
    body: Annotated[RequestQuoteRequest | None, Body()] = None,
) -> Plan:
    """Ask an agent to price this plan, with optional extras. proposed becomes requested.
    Never a price here. 404 if it is missing or not the caller's. 409 if it is not proposed
    (a second click too). 422 if an extra is unknown or no longer offered."""
    extra_ids = body.extra_ids if body is not None else []
    return Plan.of(await use_case(plan_id, client_id, extra_ids))


agent_router = APIRouter(
    prefix="/agent/plans",
    tags=["agent"],
    responses=ERRORS,
)


@agent_router.get("", operation_id="listQuoteQueue")
async def list_quote_queue(
    use_case: Annotated[ListQuoteQueue, Depends(get_list_quote_queue)],
    _: Annotated[UUID, Depends(get_current_agent_id)],
    status: Literal["requested"] = "requested",
    limit: Annotated[int, Query(ge=1, le=QUEUE_CAP)] = QUEUE_PAGE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[QueueEntry]:
    """Plans waiting for a quote, oldest first. Wish text, destination, dates, travellers, budget.
    Never a price and never a partner name: take the plan to see those."""
    return [
        QueueEntry.of(entry)
        for entry in await use_case(PlanStatus(status), limit=limit, offset=offset)
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
