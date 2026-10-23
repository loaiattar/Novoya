from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from novoya_api.wishes.domain.errors import AnswerInProgress


class InMemoryAnswersInProgress:
    """AnswersInProgress in this process's memory. Enough with one API instance (#48); with
    several, a second answer may still start a model run, and the wish's status check in
    the repository still keeps only one plan."""

    def __init__(self) -> None:
        self._held: set[UUID] = set()

    @asynccontextmanager
    async def hold(self, wish_id: UUID) -> AsyncIterator[None]:
        if wish_id in self._held:
            raise AnswerInProgress("this wish is already being answered")
        self._held.add(wish_id)
        try:
            yield
        finally:
            self._held.discard(wish_id)
