"""Composition root of the planning module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUserView, require_agent, require_client
from novoya_api.planning.application.use_cases.get_agent_plan import GetAgentPlan
from novoya_api.planning.application.use_cases.get_plan import GetPlan
from novoya_api.planning.application.use_cases.list_quote_queue import ListQuoteQueue
from novoya_api.planning.application.use_cases.request_quote import RequestQuote
from novoya_api.planning.application.use_cases.set_extra_price import SetExtraPrice
from novoya_api.planning.application.use_cases.set_item_price import SetItemPrice
from novoya_api.planning.application.use_cases.take_plan import TakePlan
from novoya_api.planning.infrastructure.catalog import PartnerOffers
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.planning.infrastructure.wish_owners import WishOwners
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


def get_request_quote(session: Annotated[AsyncSession, Depends(get_session)]) -> RequestQuote:
    return RequestQuote(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        wishes=WishOwners(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
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


def get_set_extra_price(session: Annotated[AsyncSession, Depends(get_session)]) -> SetExtraPrice:
    return SetExtraPrice(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )
