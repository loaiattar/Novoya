from typing import Protocol

from novoya_api.planning.application.dto import RequestReceivedEmail


class RequestNotifier(Protocol):
    async def send_request_received(self, email: RequestReceivedEmail) -> bool:
        """Tells the client the agency received their trip. False when sending failed: the
        error is logged, never raised, because the request is already saved."""
        ...
