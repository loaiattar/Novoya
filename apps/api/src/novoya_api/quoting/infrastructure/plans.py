from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.planning.public import quote_plan
from novoya_api.quoting.application.dto import QuotedExtra, QuotedItem, QuotedPlan


class PlanningPlans:
    """PlanQuoting through planning.public, in the request's session: the plan's new status
    and the quote are committed together."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def quote(self, plan_id: UUID, agent_id: UUID) -> QuotedPlan:
        priced = await quote_plan(plan_id, agent_id, session=self._session)
        return QuotedPlan(
            plan_id=priced.plan_id,
            wish_id=priced.wish_id,
            client_id=priced.client_id,
            agent_id=priced.agent_id,
            summary=priced.summary,
            items=tuple(
                QuotedItem(
                    day=item.day,
                    kind=item.kind,
                    title=item.title,
                    description=item.description,
                    quantity=item.quantity,
                    price=item.price,
                )
                for item in priced.items
            ),
            extras=tuple(
                QuotedExtra(
                    label=extra.label, unit=extra.unit, pricing=extra.pricing, price=extra.price
                )
                for extra in priced.extras
            ),
            total=priced.total,
            wish_text=priced.wish_text,
            country=priced.country,
            city=priced.city,
            persons=priced.persons,
            start_date=priced.start_date,
            end_date=priced.end_date,
            budget_max=priced.budget_max,
            currency=priced.currency,
            tags=priced.tags,
        )
