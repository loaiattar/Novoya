from typing import Protocol

from novoya_api.planning.application.dto import PlanRequest


class OutlineWriter(Protocol):
    async def write(self, request: PlanRequest) -> str | None:
        """An outline of the trip for the agent, from the client's text, or None when the
        model could not write one. Never shown to the client (#184)."""
        ...
