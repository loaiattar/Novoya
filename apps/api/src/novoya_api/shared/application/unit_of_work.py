from typing import Protocol


class UnitOfWork(Protocol):
    """One use case is one transaction: the use case calls commit() once, at the end.

    Nothing to do on failure: the request's database session is closed at the end of the
    request, and closing it discards everything that was not committed.
    """

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
