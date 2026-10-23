import logging
from dataclasses import asdict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import get_user
from novoya_api.planning.public import (
    ClientContact,
    PlanRequest,
    confirm_request,
    generate_plan,
    request_custom_plan,
)
from novoya_api.wishes.application.ports.planner import CustomRequest, ProposedItem, ProposedPlan
from novoya_api.wishes.domain.wish import Wish

logger = logging.getLogger(__name__)


class PartnerPlanner:
    """Planner through planning.public, in the request's session, so the plan and the
    planned wish are committed together."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def propose(self, wish: Wish) -> ProposedPlan:
        plan = await generate_plan(_request(wish), session=self._session)
        return ProposedPlan(
            id=plan.id,
            wish_id=plan.wish_id,
            status=plan.status,
            based_on_preferences=plan.based_on_preferences,
            summary=plan.summary,
            items=tuple(ProposedItem(**asdict(item)) for item in plan.items),
        )

    async def request_custom(self, wish: Wish) -> CustomRequest:
        plan = await request_custom_plan(_request(wish), session=self._session)
        return CustomRequest(id=plan.id, wish_id=plan.wish_id, status=plan.status)

    async def confirm(self, plan_id: UUID, user_id: UUID) -> None:
        # Found here: planning.public may not import accounts, which erases plans.
        try:
            user = await get_user(user_id, session=self._session)
        except Exception as error:
            logger.error("could not send the request email: %s", type(error).__name__)
            return
        if user is not None:
            await confirm_request(plan_id, ClientContact(user.email, user.name, user.locale))


def _request(wish: Wish) -> PlanRequest:
    assert wish.destination is not None and wish.answers is not None  # answered
    answers = wish.answers
    return PlanRequest(
        wish_id=wish.id,
        text=wish.text,
        country=wish.destination.country,
        city=wish.destination.city,
        tags=tuple(f"{t.section}:{t.tag}" for t in answers.selected_tags),
        persons=answers.persons,
        start_date=answers.start_date,
        end_date=answers.end_date,
        budget_max=answers.budget_max,
    )
