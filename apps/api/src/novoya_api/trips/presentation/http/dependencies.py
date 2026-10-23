"""Composition root of the trips module: plugs the adapters into the use case.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUserView, require_client
from novoya_api.config import get_settings
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.trips.application.use_cases.list_my_trips import ListMyTrips
from novoya_api.trips.infrastructure.sources import PlansOfWishes, QuotesOfPlans, WishesOfUser


def get_client_id(user: Annotated[CurrentUserView, Depends(require_client)]) -> UUID:
    """The signed-in client: 401 without a session, 403 for an agent."""
    return user.user_id.value


def get_list_my_trips(session: Annotated[AsyncSession, Depends(get_session)]) -> ListMyTrips:
    return ListMyTrips(WishesOfUser(session), PlansOfWishes(session), QuotesOfPlans(session))


def get_answer_days() -> int:
    """The answer time promised once a trip is sent: one setting (NOVOYA_QUOTE_ANSWER_DAYS)."""
    return get_settings().quote_answer_days
