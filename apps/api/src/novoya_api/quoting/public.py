"""What other modules may use from quoting. Nothing else in quoting may be imported.

- delete_for_user(user_id): erases the quotes sent to this client, with their PDF. Call it
  before planning.public.delete_for_user: a quote points to its plan. The caller commits.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.quoting.infrastructure.db.repository import SqlQuoteRepository

__all__ = ["delete_for_user"]


async def delete_for_user(user_id: UUID, *, session: AsyncSession) -> None:
    """Erase the quotes of this client, PDFs included. The caller commits."""
    await SqlQuoteRepository(session).delete_for_client(user_id)
