from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyUnitOfWork:
    """UnitOfWork on the request's session, shared with the repositories of the use case."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
