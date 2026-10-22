"""Composition root of the quoting module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated, NamedTuple
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUser, CurrentUserView, Role, require_agent
from novoya_api.config import get_settings
from novoya_api.quoting.application.use_cases.get_quote_pdf import GetQuotePdf
from novoya_api.quoting.application.use_cases.send_quote import SendQuote
from novoya_api.quoting.infrastructure.db.repository import SqlQuoteRepository
from novoya_api.quoting.infrastructure.pdf.renderer import WeasyPrintRenderer
from novoya_api.quoting.infrastructure.plans import PlanningPlans
from novoya_api.quoting.infrastructure.users import AccountPeople
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.system_clock import SystemClock

STAFF = frozenset({Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN})


class Reader(NamedTuple):
    user_id: UUID
    staff: bool  # an agent, an admin or a super admin reads every quote


def get_current_agent_id(user: Annotated[CurrentUserView, Depends(require_agent)]) -> UUID:
    """The signed-in agent: 401 without a session, 403 for a client (the admin passes)."""
    return user.user_id.value


def get_reader(user: CurrentUser) -> Reader:
    """Whoever is signed in: 401 without a session. The use case decides what they may read."""
    return Reader(user.user_id.value, user.role in STAFF)


def get_send_quote(session: Annotated[AsyncSession, Depends(get_session)]) -> SendQuote:
    return SendQuote(
        plans=PlanningPlans(session),
        people=AccountPeople(session),
        renderer=WeasyPrintRenderer(),
        quotes=SqlQuoteRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
        frontend_url=get_settings().frontend_url,
    )


def get_get_quote_pdf(session: Annotated[AsyncSession, Depends(get_session)]) -> GetQuotePdf:
    return GetQuotePdf(quotes=SqlQuoteRepository(session))
