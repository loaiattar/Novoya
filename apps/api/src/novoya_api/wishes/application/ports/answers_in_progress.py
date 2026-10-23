from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID


class AnswersInProgress(Protocol):
    def hold(self, wish_id: UUID) -> AbstractAsyncContextManager[None]:
        """Marks the wish as being answered until the block ends. Raises AnswerInProgress
        when another request holds it: building a plan costs a model run, so a second answer
        is turned away before it starts one."""
        ...
