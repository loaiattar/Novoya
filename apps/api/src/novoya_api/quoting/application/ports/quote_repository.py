from typing import Protocol
from uuid import UUID

from novoya_api.quoting.domain.quote import Quote


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
