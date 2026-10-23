import logging
from collections.abc import Sequence
from uuid import UUID

from novoya_api.planning.application.dto import PlanView, RequestReceivedEmail
from novoya_api.planning.application.plan_view import plan_as_view
from novoya_api.planning.application.ports.clients import ClientDirectory
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.request_notifier import RequestNotifier
from novoya_api.planning.application.ports.wish_ownership import WishOwnership
from novoya_api.planning.domain.errors import InvalidPlan, PlanNotFound
from novoya_api.planning.domain.plan import PlanExtra
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class RequestQuote:
    """The owner sends the trip to the agency, with the extras they chose. proposed becomes
    requested. Anyone else looks like not found. An extra the catalog does not list is a 422.
    After the commit, the client gets one email saying when to expect the answer: a second
    send is an invalid transition before anything is saved or sent (#168)."""

    def __init__(
        self,
        plans: PlanRepository,
        catalog: OfferCatalog,
        wishes: WishOwnership,
        uow: UnitOfWork,
        clock: Clock,
        clients: ClientDirectory,
        notifier: RequestNotifier,
        frontend_url: str,
        answer_days: int,
    ) -> None:
        self._plans = plans
        self._catalog = catalog
        self._wishes = wishes
        self._uow = uow
        self._clock = clock
        self._clients = clients
        self._notifier = notifier
        self._frontend_url = frontend_url.rstrip("/")
        self._answer_days = answer_days

    async def __call__(
        self, plan_id: UUID, client_id: UUID, extra_ids: Sequence[UUID] = ()
    ) -> PlanView:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        owner_id = await self._wishes.owner_id(plan.wish_id)
        if owner_id is None or owner_id != client_id:
            raise PlanNotFound("no such plan")
        plan.request_quote(self._clock.now(), await self._extras(extra_ids))
        await self._plans.save(plan)
        kept_ids = [item.offer_id for item in plan.items if not item.removed]
        offers = {offer.id: offer for offer in await self._catalog.summaries_for(kept_ids)}
        await self._uow.commit()

        # After the commit: a failed email never undoes the request.
        await self._confirm(client_id, plan.id)
        return plan_as_view(plan, offers)

    async def _confirm(self, client_id: UUID, plan_id: UUID) -> None:
        """Email the client that the agency has the trip. The request is saved already, so any
        error here, the account lookup too, is logged by its type only (it can hold the
        address) and never raised."""
        try:
            client = await self._clients.contact(client_id)
            if client is None:
                return
            await self._notifier.send_request_received(
                RequestReceivedEmail(
                    to=client.email,
                    name=client.name,
                    locale=client.locale,
                    plan_url=f"{self._frontend_url}/plans/{plan_id}",
                    answer_days=self._answer_days,
                )
            )
        except Exception as error:
            logger.error("could not send the request email: %s", type(error).__name__)

    async def _extras(self, extra_ids: Sequence[UUID]) -> list[PlanExtra]:
        """A snapshot of each chosen extra: a supplement keeps today's amount."""
        wanted = list(dict.fromkeys(extra_ids))
        if not wanted:
            return []
        found = {extra.id: extra for extra in await self._catalog.extras_for(wanted)}
        if any(extra_id not in found for extra_id in wanted):
            raise InvalidPlan("an extra is not available")
        return [
            PlanExtra(
                extra_id=extra_id,
                pricing=found[extra_id].pricing,
                price_eur=found[extra_id].supplement_eur,
                label=found[extra_id].label,
                unit=found[extra_id].unit,
            )
            for extra_id in wanted
        ]
