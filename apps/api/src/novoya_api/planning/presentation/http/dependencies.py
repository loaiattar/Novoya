"""Composition root of the planning module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUserView, require_agent, require_client
from novoya_api.config import get_settings
from novoya_api.planning.application.ports.request_notifier import RequestNotifier
from novoya_api.planning.application.use_cases.get_admin_plan import GetAdminPlan
from novoya_api.planning.application.use_cases.get_agent_plan import GetAgentPlan
from novoya_api.planning.application.use_cases.get_plan import GetPlan
from novoya_api.planning.application.use_cases.list_admin_plans import ListAdminPlans
from novoya_api.planning.application.use_cases.list_quote_queue import ListQuoteQueue
from novoya_api.planning.application.use_cases.plan_offers import AddPlanItem, ListPlanOffers
from novoya_api.planning.application.use_cases.request_quote import RequestQuote
from novoya_api.planning.application.use_cases.set_extra_price import SetExtraPrice
from novoya_api.planning.application.use_cases.set_item_price import SetItemPrice
from novoya_api.planning.application.use_cases.take_plan import TakePlan
from novoya_api.planning.infrastructure.catalog import PartnerOffers
from novoya_api.planning.infrastructure.clients import AccountClients
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.planning.infrastructure.email.smtp_request_notifier import smtp_request_notifier
from novoya_api.planning.infrastructure.people import AccountPeople
from novoya_api.planning.infrastructure.wish_owners import WishOwners
from novoya_api.planning.infrastructure.wish_search import WishesSearch
from novoya_api.planning.infrastructure.wish_trips import WishTrips
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.system_clock import SystemClock


def get_current_user_id(user: Annotated[CurrentUserView, Depends(require_client)]) -> UUID:
    """The signed-in client: 401 without a session, 403 for an agent (the admin passes)."""
    return user.user_id.value


def get_get_plan(session: Annotated[AsyncSession, Depends(get_session)]) -> GetPlan:
    return GetPlan(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        wishes=WishOwners(session),
    )


def get_answer_days() -> int:
    """The answer time promised to the client, in days: one setting (NOVOYA_QUOTE_ANSWER_DAYS)."""
    return get_settings().quote_answer_days


def get_request_notifier() -> RequestNotifier:
    """The same NOVOYA_SMTP_* settings as the other emails."""
    return smtp_request_notifier()


def get_request_quote(
    session: Annotated[AsyncSession, Depends(get_session)],
    client_id: Annotated[UUID, Depends(get_current_user_id)],
) -> RequestQuote:
    return RequestQuote(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        # FOR SHARE on the client's own wish: a preference removal in progress finishes
        # first (#165). Someone else's wish is not locked.
        wishes=WishOwners(session, lock_for=client_id),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
        clients=AccountClients(session),
        notifier=get_request_notifier(),
        frontend_url=get_settings().frontend_url,
        answer_days=get_answer_days(),
    )


def get_current_agent_id(user: Annotated[CurrentUserView, Depends(require_agent)]) -> UUID:
    """The signed-in agent: 401 without a session, 403 for a client (the admin passes)."""
    return user.user_id.value


def get_list_quote_queue(session: Annotated[AsyncSession, Depends(get_session)]) -> ListQuoteQueue:
    return ListQuoteQueue(plans=SqlPlanRepository(session), trips=WishTrips(session))


def get_take_plan(session: Annotated[AsyncSession, Depends(get_session)]) -> TakePlan:
    return TakePlan(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )


def get_get_agent_plan(session: Annotated[AsyncSession, Depends(get_session)]) -> GetAgentPlan:
    return GetAgentPlan(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
    )


def get_set_item_price(session: Annotated[AsyncSession, Depends(get_session)]) -> SetItemPrice:
    return SetItemPrice(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )


def get_list_plan_offers(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListPlanOffers:
    return ListPlanOffers(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
    )


def get_add_plan_item(session: Annotated[AsyncSession, Depends(get_session)]) -> AddPlanItem:
    return AddPlanItem(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )


def get_set_extra_price(session: Annotated[AsyncSession, Depends(get_session)]) -> SetExtraPrice:
    return SetExtraPrice(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )


def get_list_admin_plans(session: Annotated[AsyncSession, Depends(get_session)]) -> ListAdminPlans:
    return ListAdminPlans(
        plans=SqlPlanRepository(session),
        trips=WishTrips(session),
        wishes=WishesSearch(session),
        people=AccountPeople(session),
    )


def get_get_admin_plan(session: Annotated[AsyncSession, Depends(get_session)]) -> GetAdminPlan:
    return GetAdminPlan(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        people=AccountPeople(session),
    )
