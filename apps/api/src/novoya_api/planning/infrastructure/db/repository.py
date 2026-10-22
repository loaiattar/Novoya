from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.planning.application.ports.plan_repository import QUEUE_PAGE, ItemWrite
from novoya_api.planning.domain.errors import InvalidPlan, PlanNotFound
from novoya_api.planning.domain.plan import Plan, PlanExtra, PlanItem, PlanStatus
from novoya_api.planning.infrastructure.db.models import PlanExtraModel, PlanItemModel, PlanModel
from novoya_api.shared.domain.errors import InvalidTransition


class SqlPlanRepository:
    """PlanRepository on PostgreSQL. Maps the entity to rows; the caller commits.

    save() writes the plan row only, and only if its status is still the one this request
    read: a late request-quote must not overwrite an agent's take. When the plan leaves
    proposed, save() also inserts the chosen extras; their prices go through save_extra().
    Item prices go through save_item(), which writes only the columns of that patch, so a
    stale tab cannot undo a removal or roll a newer price back. A removal locks the plan row
    and counts kept items in the database, so two tabs cannot drop the last item.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._read_status: dict[UUID, str] = {}

    async def add(self, plan: Plan) -> None:
        self._session.add(
            PlanModel(
                id=plan.id,
                wish_id=plan.wish_id,
                status=plan.status.value,
                based_on_preferences=plan.based_on_preferences,
                summary=plan.summary,
                assigned_agent_id=plan.assigned_agent_id,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
            )
        )
        # The plan row first: plan_items points to it, and the unit of work does not know.
        await self._session.flush()
        self._session.add_all(
            PlanItemModel(
                id=item.id,
                plan_id=plan.id,
                offer_id=item.offer_id,
                day=item.day,
                quantity=item.quantity,
                note=item.note,
                negotiated_price=item.negotiated_price,
                removed=item.removed,
            )
            for item in plan.items
        )
        self._read_status[plan.id] = plan.status.value

    async def delete_for_wishes(self, wish_ids: Sequence[UUID]) -> None:
        """Erase the plans of these wishes; their items and extras go with them (cascade).
        The caller commits."""
        if not wish_ids:
            return
        await self._session.execute(
            delete(PlanModel)
            .where(PlanModel.wish_id.in_(wish_ids))
            .execution_options(synchronize_session=False)
        )

    async def get(self, plan_id: UUID) -> Plan | None:
        row = await self._session.get(PlanModel, plan_id, populate_existing=True)
        if row is None:
            return None
        items = await self._session.scalars(
            select(PlanItemModel)
            .where(PlanItemModel.plan_id == plan_id)
            .order_by(PlanItemModel.day, PlanItemModel.id)
            .execution_options(populate_existing=True)
        )
        extras = await self._session.scalars(
            select(PlanExtraModel)
            .where(PlanExtraModel.plan_id == plan_id)
            .order_by(PlanExtraModel.extra_id)
            .execution_options(populate_existing=True)
        )
        return self._to_plan(row, items, extras)

    async def list_queue(
        self,
        statuses: Sequence[PlanStatus],
        agent_id: UUID,
        *,
        limit: int = QUEUE_PAGE,
        offset: int = 0,
    ) -> list[Plan]:
        mine = [status.value for status in statuses if status is not PlanStatus.REQUESTED]
        conditions = []
        if PlanStatus.REQUESTED in statuses:
            conditions.append(PlanModel.status == PlanStatus.REQUESTED.value)
        if mine:
            conditions.append(
                and_(PlanModel.status.in_(mine), PlanModel.assigned_agent_id == agent_id)
            )
        if not conditions:
            return []
        rows = (
            await self._session.scalars(
                select(PlanModel)
                .where(or_(*conditions))
                .order_by(PlanModel.updated_at, PlanModel.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return [self._to_plan(row, ()) for row in rows]

    async def search(
        self,
        statuses: Sequence[PlanStatus],
        wish_ids: Sequence[UUID] | None,
        *,
        limit: int = QUEUE_PAGE,
        offset: int = 0,
    ) -> list[Plan]:
        statement = select(PlanModel)
        if statuses:
            statement = statement.where(PlanModel.status.in_([s.value for s in statuses]))
        if wish_ids is not None:
            statement = statement.where(PlanModel.wish_id.in_(wish_ids))
        rows = await self._session.scalars(
            statement.order_by(PlanModel.updated_at.desc(), PlanModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [self._to_plan(row, ()) for row in rows]

    async def count_by_status(self) -> dict[str, int]:
        """Every plan by status. Statuses with no plan are left out."""
        rows = await self._session.execute(
            select(PlanModel.status, func.count()).group_by(PlanModel.status)
        )
        return {status: count for status, count in rows}

    async def list_by_ids(self, plan_ids: Sequence[UUID]) -> list[Plan]:
        """These plans, without their items. Missing ids are omitted."""
        if not plan_ids:
            return []
        rows = await self._session.scalars(select(PlanModel).where(PlanModel.id.in_(plan_ids)))
        return [self._to_plan(row, ()) for row in rows]

    def _to_plan(
        self,
        row: PlanModel,
        items: Iterable[PlanItemModel],
        extras: Iterable[PlanExtraModel] = (),
    ) -> Plan:
        self._read_status[row.id] = row.status
        return Plan(
            id=row.id,
            wish_id=row.wish_id,
            status=PlanStatus(row.status),
            based_on_preferences=row.based_on_preferences,
            summary=row.summary,
            items=tuple(
                PlanItem(
                    id=item.id,
                    offer_id=item.offer_id,
                    day=item.day,
                    quantity=item.quantity,
                    note=item.note,
                    negotiated_price=item.negotiated_price,
                    removed=item.removed,
                )
                for item in items
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
            assigned_agent_id=row.assigned_agent_id,
            extras=tuple(
                PlanExtra(
                    extra_id=extra.extra_id,
                    pricing=extra.pricing,
                    price_eur=extra.price_eur,
                    label=extra.label,
                    unit=extra.unit,
                    confirmed=extra.confirmed,
                )
                for extra in extras
            ),
        )

    async def save(self, plan: Plan) -> None:
        read_status = self._read_status[plan.id]  # KeyError: save() without get() or add()
        result = await self._session.execute(
            update(PlanModel)
            .where(PlanModel.id == plan.id, PlanModel.status == read_status)
            .values(
                status=plan.status.value,
                based_on_preferences=plan.based_on_preferences,
                summary=plan.summary,
                assigned_agent_id=plan.assigned_agent_id,
                updated_at=plan.updated_at,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise InvalidTransition("the plan changed meanwhile, reload it")
        if read_status == PlanStatus.PROPOSED.value and plan.status is not PlanStatus.PROPOSED:
            self._session.add_all(
                PlanExtraModel(
                    plan_id=plan.id,
                    extra_id=extra.extra_id,
                    pricing=extra.pricing,
                    price_eur=extra.price_eur,
                    label=extra.label,
                    unit=extra.unit,
                    confirmed=extra.confirmed,
                )
                for extra in plan.extras
            )
        self._read_status[plan.id] = plan.status.value

    async def save_extra(self, plan: Plan, extra_id: UUID) -> None:
        read_status = self._read_status[plan.id]  # KeyError: save_extra() without get() or add()
        extra = next((entry for entry in plan.extras if entry.extra_id == extra_id), None)
        if extra is None:
            raise PlanNotFound("no such extra on this plan")
        result = await self._session.execute(
            update(PlanModel)
            .where(PlanModel.id == plan.id, PlanModel.status == read_status)
            .values(updated_at=plan.updated_at)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise InvalidTransition("the plan changed meanwhile, reload it")
        written = await self._session.execute(
            update(PlanExtraModel)
            .where(PlanExtraModel.plan_id == plan.id, PlanExtraModel.extra_id == extra_id)
            .values(price_eur=extra.price_eur, confirmed=extra.confirmed)
            .execution_options(synchronize_session=False)
        )
        if written.rowcount != 1:
            raise PlanNotFound("no such extra on this plan")

    async def save_item(self, plan: Plan, item_id: UUID, write: ItemWrite) -> None:
        read_status = self._read_status[plan.id]  # KeyError: save_item() without get() or add()
        item = next((entry for entry in plan.items if entry.id == item_id), None)
        if item is None:
            raise PlanNotFound("no such item")
        if write is ItemWrite.REMOVE:
            # Lock this plan so two removals run one after the other; then count in the database.
            await self._session.execute(
                select(PlanModel.id).where(PlanModel.id == plan.id).with_for_update()
            )
            others_kept = await self._session.scalar(
                select(func.count())
                .select_from(PlanItemModel)
                .where(
                    PlanItemModel.plan_id == plan.id,
                    PlanItemModel.id != item.id,
                    PlanItemModel.removed.is_(False),
                )
            )
            if others_kept == 0:
                raise InvalidPlan("a plan needs at least one item")
        result = await self._session.execute(
            update(PlanModel)
            .where(PlanModel.id == plan.id, PlanModel.status == read_status)
            .values(updated_at=plan.updated_at)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise InvalidTransition("the plan changed meanwhile, reload it")
        written = await self._session.execute(
            self._item_update(plan.id, item, write).execution_options(synchronize_session=False)
        )
        if written.rowcount != 1:
            if write is ItemWrite.PRICE:
                raise InvalidTransition("the plan changed meanwhile, reload it")
            raise PlanNotFound("no such item")

    def _item_update(self, plan_id: UUID, item: PlanItem, write: ItemWrite):
        row = (PlanItemModel.id == item.id, PlanItemModel.plan_id == plan_id)
        if write is ItemWrite.PRICE:
            return (
                update(PlanItemModel)
                .where(*row, PlanItemModel.removed.is_(False))
                .values(negotiated_price=item.negotiated_price)
            )
        if write is ItemWrite.REMOVE:
            return update(PlanItemModel).where(*row).values(removed=True, negotiated_price=None)
        return update(PlanItemModel).where(*row).values(removed=False)
