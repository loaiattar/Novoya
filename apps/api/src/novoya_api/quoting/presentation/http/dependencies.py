"""Composition root of the quoting module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from functools import lru_cache
from typing import Annotated, NamedTuple
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUser, CurrentUserView, Role, require_agent
from novoya_api.config import get_settings
from novoya_api.quoting.application.ports.notifier import QuoteNotifier
from novoya_api.quoting.application.use_cases.answer_quote import AnswerQuote
from novoya_api.quoting.application.use_cases.get_plan_quote import GetPlanQuote
from novoya_api.quoting.application.use_cases.get_quote import GetQuote
from novoya_api.quoting.application.use_cases.get_quote_pdf import GetQuotePdf
from novoya_api.quoting.application.use_cases.resend_quote_email import ResendQuoteEmail
from novoya_api.quoting.application.use_cases.send_quote import SendQuote
from novoya_api.quoting.infrastructure.db.repository import SqlQuoteRepository
from novoya_api.quoting.infrastructure.email.smtp_quote_notifier import SmtpQuoteNotifier
from novoya_api.quoting.infrastructure.pdf.renderer import WeasyPrintRenderer
from novoya_api.quoting.infrastructure.plans import PlanningPlans
from novoya_api.quoting.infrastructure.users import AccountPeople
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.shared.infrastructure.system_clock import SystemClock

STAFF = frozenset({Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN})


class Reader(NamedTuple):
    user_id: UUID
    staff: bool  # an agent, an admin or a super admin reads every quote


class Staff(NamedTuple):
    user_id: UUID
    admin: bool  # an admin may resend any quote's email


def get_current_agent_id(user: Annotated[CurrentUserView, Depends(require_agent)]) -> UUID:
    """The signed-in agent: 401 without a session, 403 for a client (the admin passes)."""
    return user.user_id.value


def get_staff(user: Annotated[CurrentUserView, Depends(require_agent)]) -> Staff:
    """The signed-in agent or admin: 401 without a session, 403 for a client."""
    return Staff(user.user_id.value, user.role in (Role.ADMIN, Role.SUPER_ADMIN))


def get_reader(user: CurrentUser) -> Reader:
    """Whoever is signed in: 401 without a session. The use case decides what they may read."""
    return Reader(user.user_id.value, user.role in STAFF)


def get_notifier() -> QuoteNotifier:
    """The same NOVOYA_SMTP_* settings as the accounts emails."""
    settings = get_settings()
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
    return SmtpQuoteNotifier(
        settings.smtp_host,
        settings.smtp_port,
        settings.mail_from,
        username=settings.smtp_username,
        password=password,
        start_tls=settings.smtp_start_tls,
    )


# Built once: it holds the counters of the resent emails.
@lru_cache
def get_rate_limiter() -> RateLimiter:
    return InMemoryRateLimiter(SystemClock())


def get_send_quote(session: Annotated[AsyncSession, Depends(get_session)]) -> SendQuote:
    return SendQuote(
        plans=PlanningPlans(session),
        people=AccountPeople(session),
        renderer=WeasyPrintRenderer(),
        quotes=SqlQuoteRepository(session),
        notifier=get_notifier(),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
        frontend_url=get_settings().frontend_url,
    )


def get_get_quote_pdf(session: Annotated[AsyncSession, Depends(get_session)]) -> GetQuotePdf:
    return GetQuotePdf(quotes=SqlQuoteRepository(session))


def get_resend_quote_email(
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> ResendQuoteEmail:
    return ResendQuoteEmail(
        quotes=SqlQuoteRepository(session),
        plans=PlanningPlans(session),
        people=AccountPeople(session),
        notifier=get_notifier(),
        rate_limiter=rate_limiter,
        frontend_url=get_settings().frontend_url,
    )


def get_get_plan_quote(session: Annotated[AsyncSession, Depends(get_session)]) -> GetPlanQuote:
    return GetPlanQuote(quotes=SqlQuoteRepository(session))


def get_get_quote(session: Annotated[AsyncSession, Depends(get_session)]) -> GetQuote:
    return GetQuote(
        quotes=SqlQuoteRepository(session),
        plans=PlanningPlans(session),
        people=AccountPeople(session),
        clock=SystemClock(),
    )


def get_answer_quote(session: Annotated[AsyncSession, Depends(get_session)]) -> AnswerQuote:
    return AnswerQuote(
        quotes=SqlQuoteRepository(session),
        plans=PlanningPlans(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )
