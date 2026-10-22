from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from novoya_api.quoting.domain.quote import Quote, QuoteStatus

ADMIN_PAGE = 50
ADMIN_CAP = 100


class QuoteRepository(Protocol):
    async def add(self, quote: Quote) -> None:
        """Adds the quote with its PDF. One quote per plan: a second one fails."""
        ...

    async def get(self, quote_id: UUID, with_pdf: bool = True) -> Quote | None:
        """The quote, or None. with_pdf=False skips reading the file: its pdf is None."""
        ...

    async def get_for_plan(self, plan_id: UUID) -> Quote | None:
        """The plan's quote without its PDF (pdf is None), or None before it is sent. A
        plan has at most one."""
        ...

    async def save_answer(self, quote: Quote) -> None:
        """Writes the quote's answer, decided_at and client_comment. Raises
        QuoteAlreadyAnswered when the stored quote has an answer already."""
        ...

    async def search(
        self,
        plan_ids: Sequence[UUID] | None,
        status: QuoteStatus | None,
        now: datetime,
        *,
        limit: int = ADMIN_PAGE,
        offset: int = 0,
    ) -> list[Quote]:
        """Every client's quotes, newest first, without their PDF. plan_ids None means every
        plan; status keeps the quotes that have it at `now`, as Quote.status says."""
        ...
