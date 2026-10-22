"""What other modules may use from quoting. Nothing else in quoting may be imported.

- delete_for_user(user_id): erases the quotes sent to this client, with their PDF. Call it
  before planning.public.delete_for_user: a quote points to its plan. The caller commits.
- count_quotes_by_status(now) -> {status: count}: open, expired, accepted, rejected, as
  GET /quotes/{id} gives them, for the admin dashboard. Counts only.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.quoting.infrastructure.db.repository import SqlQuoteRepository

__all__ = ["count_quotes_by_status", "delete_for_user"]


async def delete_for_user(user_id: UUID, *, session: AsyncSession) -> None:
    """Erase the quotes of this client, PDFs included. The caller commits."""
    await SqlQuoteRepository(session).delete_for_client(user_id)


async def count_quotes_by_status(now: datetime, *, session: AsyncSession) -> dict[str, int]:
    """How many quotes have each status at `now`. For admins only: the caller's router must
    require the admin role."""
    found = await SqlQuoteRepository(session).count_by_status(now)
    return {status.value: count for status, count in found.items()}
