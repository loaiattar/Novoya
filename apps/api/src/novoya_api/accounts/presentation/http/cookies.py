"""The session cookie: an opaque token, HttpOnly, SameSite=Lax.

In production (HTTPS) it is Secure and named with the __Host- prefix, which also forbids a
Domain attribute, so a subdomain cannot overwrite it. Locally (HTTP) it is plain.
"""

import re

from fastapi import Request, Response

from novoya_api.accounts.domain.value_objects import SessionToken
from novoya_api.config import Settings


def cookie_name(settings: Settings) -> str:
    return "__Host-novoya_session" if settings.session_cookie_secure else "novoya_session"


def read_session_cookie(request: Request, settings: Settings) -> SessionToken | None:
    value = request.cookies.get(cookie_name(settings))
    return SessionToken(value) if value else None


def set_session_cookie(response: Response, token: SessionToken, settings: Settings) -> None:
    response.set_cookie(
        cookie_name(settings),
        token.value,
        max_age=settings.session_absolute_ttl_days * 24 * 3600,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        cookie_name(settings),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


# The OAuth state cookie ties a provider sign-in to the browser that started it (login CSRF).
# SameSite=Lax is enough: the provider sends the browser back with a top-level GET.

STATE_COOKIE_SECONDS = 600  # as long as the state itself
# One cookie per sign-in, named after the start of its state: a double click or a second tab
# starts another sign-in without breaking the first. The state comes from the URL, so only
# the characters our states use may end up in a cookie name.
_STATE_KEY = re.compile(r"[A-Za-z0-9_-]{1,16}")


def state_cookie_name(settings: Settings, state: str) -> str | None:
    key = state[:16]
    if not _STATE_KEY.fullmatch(key):
        return None
    prefix = "__Host-" if settings.session_cookie_secure else ""
    return f"{prefix}novoya_oauth_state_{key}"


def read_state_cookie(request: Request, settings: Settings, state: str) -> str | None:
    name = state_cookie_name(settings, state)
    return (request.cookies.get(name) or None) if name else None


def set_state_cookie(response: Response, state: str, settings: Settings) -> None:
    name = state_cookie_name(settings, state)
    if name is None:  # never for the states we generate
        return
    response.set_cookie(
        name,
        state,
        max_age=STATE_COOKIE_SECONDS,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_state_cookie(response: Response, settings: Settings, state: str | None) -> None:
    name = state_cookie_name(settings, state) if state else None
    if name is None:
        return
    response.delete_cookie(
        name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
