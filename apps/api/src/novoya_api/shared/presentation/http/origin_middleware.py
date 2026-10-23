"""CSRF guard: refuse state-changing browser requests that come from another site.

The session cookie is SameSite=Lax, which already blocks cross-site POSTs. This checks the
Origin header of POST, PUT, PATCH and DELETE requests against the allowed origins as well.
Requests without an Origin header (curl, server-to-server, tests) are not from a browser
form on another site, so they pass. Same-origin requests pass too, for example from the
API's own docs page (/docs).
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class OriginCheckMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed_origins = {origin.rstrip("/") for origin in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in UNSAFE_METHODS:
            headers = dict(scope["headers"])
            origin = headers.get(b"origin")
            own_origin = f"{scope['scheme']}://{headers.get(b'host', b'').decode()}"
            allowed = self.allowed_origins | {own_origin}
            if origin is not None and origin.decode().rstrip("/") not in allowed:
                response = JSONResponse(
                    {"code": "forbidden_origin", "detail": "origin not allowed"}, status_code=403
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
