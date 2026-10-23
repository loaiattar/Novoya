from collections.abc import Sequence
from typing import Protocol

from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination


class PanelBuilder(Protocol):
    """Turns the wish and the catalog tags at the destination into the preference panel."""

    async def build(self, text: str, destination: Destination, tags: Sequence[str]) -> Panel: ...
