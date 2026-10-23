import logging
from uuid import UUID

from novoya_api.planning.application.dto import ClientContact, RequestReceivedEmail
from novoya_api.planning.application.ports.clients import ClientDirectory
from novoya_api.planning.application.ports.request_notifier import RequestNotifier

logger = logging.getLogger(__name__)


class RequestConfirmation:
    """The email telling the client the agency has their trip (#168), for a plan sent with
    its items and for a custom request (#184) alike. Call it after the commit: the request is
    saved already, so any error here, the account lookup too, is logged by its type only (it
    can hold the address) and never raised."""

    def __init__(self, notifier: RequestNotifier, frontend_url: str, answer_days: int) -> None:
        self._notifier = notifier
        self._frontend_url = frontend_url.rstrip("/")
        self._answer_days = answer_days

    async def send(self, clients: ClientDirectory, client_id: UUID, plan_id: UUID) -> None:
        """Find the client, then send_to them."""
        try:
            client = await clients.contact(client_id)
        except Exception as error:
            logger.error("could not send the request email: %s", type(error).__name__)
            return
        if client is not None:
            await self.send_to(client, plan_id)

    async def send_to(self, client: ClientContact, plan_id: UUID) -> None:
        try:
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
