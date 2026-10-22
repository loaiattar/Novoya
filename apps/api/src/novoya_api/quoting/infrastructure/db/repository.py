from collections.abc import Sequence
from datetime import datetime, time
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from novoya_api.quoting.domain.errors import QuoteAlreadyAnswered
from novoya_api.quoting.domain.quote import AGENCY_TIMEZONE, Quote, QuoteStatus, paris_day
from novoya_api.quoting.infrastructure.db.models import QuoteModel
from novoya_api.shared.domain.value_objects import Locale


class SqlQuoteRepository:
    """QuoteRepository on PostgreSQL. The PDF is stored with the quote (ADR 0013)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ids_for_plans(self, plan_ids: Sequence[UUID]) -> dict[UUID, UUID]:
        """The id of the quote of each of these plans, keyed by plan id."""
        if not plan_ids:
            return {}
        rows = await self._session.execute(
            select(QuoteModel.plan_id, QuoteModel.id).where(QuoteModel.plan_id.in_(plan_ids))
        )
        return {plan_id: quote_id for plan_id, quote_id in rows}

    async def add(self, quote: Quote) -> None:
        # uq_quotes_plan_id is the last guard against a second quote for the plan; the plan's
        # own status check (409) normally stops it first.
        self._session.add(
            QuoteModel(
                id=quote.id,
                number=quote.number,
                plan_id=quote.plan_id,
                client_id=quote.client_id,
                agent_id=quote.agent_id,
                total_price=quote.total,
                currency=quote.currency,
                locale=quote.locale.value,
                sent_at=quote.sent_at,
                valid_until=quote.valid_until,
                pdf=quote.pdf,
                answer=None if quote.answer is None else quote.answer.value,
                decided_at=quote.decided_at,
                client_comment=quote.client_comment,
            )
        )
        await self._session.flush()

    async def get(self, quote_id: UUID, with_pdf: bool = True) -> Quote | None:
        # populate_existing: a row this session read earlier without its PDF is read again,
        # so row.pdf never lazy-loads (that fails under asyncio).
        options = () if with_pdf else (defer(QuoteModel.pdf),)
        row = await self._session.get(
            QuoteModel, quote_id, options=options, populate_existing=with_pdf
        )
        return None if row is None else self._to_quote(row, with_pdf)

    async def get_for_plan(self, plan_id: UUID) -> Quote | None:
        """Without the PDF: the agent's page shows the quote, the file downloads apart."""
        row = await self._session.scalar(
            select(QuoteModel).where(QuoteModel.plan_id == plan_id).options(defer(QuoteModel.pdf))
        )
        return None if row is None else self._to_quote(row, with_pdf=False)

    @staticmethod
    def _to_quote(row: QuoteModel, with_pdf: bool) -> Quote:
        return Quote(
            id=row.id,
            number=row.number,
            plan_id=row.plan_id,
            client_id=row.client_id,
            agent_id=row.agent_id,
            total=row.total_price,
            currency=row.currency,
            locale=Locale(row.locale),
            sent_at=row.sent_at,
            valid_until=row.valid_until,
            pdf=row.pdf if with_pdf else None,
            answer=None if row.answer is None else QuoteStatus(row.answer),
            decided_at=row.decided_at,
            client_comment=row.client_comment,
        )

    async def search(
        self,
        plan_ids: Sequence[UUID] | None,
        status: QuoteStatus | None,
        now: datetime,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Quote]:
        # A list never needs the PDF (about 23 KB a quote): it stays in the database.
        statement = select(QuoteModel).options(defer(QuoteModel.pdf))
        if plan_ids is not None:
            statement = statement.where(QuoteModel.plan_id.in_(plan_ids))
        if status in (QuoteStatus.ACCEPTED, QuoteStatus.REJECTED):
            statement = statement.where(QuoteModel.answer == status.value)
        elif status is not None:
            today = _start_of_today(now)
            statement = statement.where(
                QuoteModel.answer.is_(None),
                QuoteModel.valid_until < today
                if status is QuoteStatus.EXPIRED
                else QuoteModel.valid_until >= today,
            )
        rows = await self._session.scalars(
            statement.order_by(QuoteModel.sent_at.desc(), QuoteModel.id).limit(limit).offset(offset)
        )
        return [self._to_quote(row, with_pdf=False) for row in rows]

    async def count_by_status(self, now: datetime) -> dict[QuoteStatus, int]:
        """Every quote by its status at `now`, as Quote.status gives it."""
        today = _start_of_today(now)
        unanswered = QuoteModel.answer.is_(None)
        row = (
            await self._session.execute(
                select(
                    func.count().filter(unanswered, QuoteModel.valid_until >= today),
                    func.count().filter(unanswered, QuoteModel.valid_until < today),
                    func.count().filter(QuoteModel.answer == QuoteStatus.ACCEPTED.value),
                    func.count().filter(QuoteModel.answer == QuoteStatus.REJECTED.value),
                )
            )
        ).one()
        statuses = (
            QuoteStatus.OPEN,
            QuoteStatus.EXPIRED,
            QuoteStatus.ACCEPTED,
            QuoteStatus.REJECTED,
        )
        return dict(zip(statuses, row, strict=True))

    async def save_answer(self, quote: Quote) -> None:
        """Writes the client's answer, only if the row has none yet: of two answers sent at
        once, the second fails. The caller commits."""
        result = await self._session.execute(
            update(QuoteModel)
            .where(QuoteModel.id == quote.id, QuoteModel.answer.is_(None))
            .values(
                answer=None if quote.answer is None else quote.answer.value,
                decided_at=quote.decided_at,
                client_comment=quote.client_comment,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise QuoteAlreadyAnswered("the quote is already answered")

    async def delete_for_client(self, client_id: UUID) -> None:
        """Erase this client's quotes; the PDF is a column, so it goes too. The caller commits."""
        await self._session.execute(
            delete(QuoteModel)
            .where(QuoteModel.client_id == client_id)
            .execution_options(synchronize_session=False)
        )


def _start_of_today(now: datetime) -> datetime:
    """Quote.has_expired in SQL: a quote valid before this moment has expired, since the
    whole validity day counts, in Paris."""
    return datetime.combine(paris_day(now), time.min, tzinfo=AGENCY_TIMEZONE)
