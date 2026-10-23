from typing import Protocol

from novoya_api.quoting.application.dto import QuoteEmail


class QuoteNotifier(Protocol):
    async def send_quote_ready(self, email: QuoteEmail) -> bool:
        """Tells the client their quote is in their account. False when sending failed: the
        error is logged, never raised, because the quote is already saved."""
        ...
