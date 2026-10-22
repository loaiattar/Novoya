from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from novoya_api.quoting.domain.quote import Quote, QuoteStatus
from novoya_api.quoting.infrastructure.db.models import QuoteModel
from novoya_api.shared.domain.value_objects import Locale


class SqlQuoteRepository:
    """QuoteRepository on PostgreSQL. The PDF is stored with the quote (ADR 0013)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        if row is None:
            return None
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
        )

    async def delete_for_client(self, client_id: UUID) -> None:
        """Erase this client's quotes; the PDF is a column, so it goes too. The caller commits."""
        await self._session.execute(
            delete(QuoteModel)
            .where(QuoteModel.client_id == client_id)
            .execution_options(synchronize_session=False)
        )
