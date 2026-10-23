from novoya_api.planning.application.dto import PlanRequest, PlanView
from novoya_api.planning.application.plan_view import plan_as_view
from novoya_api.planning.application.ports.outline_writer import OutlineWriter
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.domain.plan import Plan
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork

# The queue shows it as the plan's title; the client's page has its own words.
CUSTOM_SUMMARY = "A custom request: no partner offer fits these dates and this group."


class RequestCustomPlan:
    """Send an answered wish to the agency although no offer fits it (#184): a custom plan,
    requested at once, with no item. Its agent builds it from the back office. The caller
    commits, then sends the confirmation email (RequestConfirmation).

    A model may draft an outline of the trip from the client's text, for the agent only. Like
    GeneratePlan, the read ends before the model runs: call it before the caller writes."""

    def __init__(
        self, writer: OutlineWriter, plans: PlanRepository, uow: UnitOfWork, clock: Clock
    ) -> None:
        self._writer = writer
        self._plans = plans
        self._uow = uow
        self._clock = clock

    async def __call__(self, request: PlanRequest) -> PlanView:
        await self._uow.rollback()
        outline = await self._writer.write(request)
        plan = Plan.custom_request(
            request.wish_id, bool(request.tags), CUSTOM_SUMMARY, outline, self._clock.now()
        )
        await self._plans.add(plan)
        return plan_as_view(plan, {})
