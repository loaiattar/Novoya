from typing import Protocol

from novoya_api.quoting.application.dto import QuoteDocument


class QuoteRenderer(Protocol):
    def render(self, document: QuoteDocument) -> bytes:
        """The quote as a PDF, in the quote's language."""
        ...
