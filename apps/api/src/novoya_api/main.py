import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novoya_api.accounts.presentation.http.router import router as accounts_router
from novoya_api.accounts.public import delete_expired_sign_ins
from novoya_api.catalog.presentation.http.router import router as catalog_router
from novoya_api.config import get_settings
from novoya_api.dashboard.presentation.http.router import router as dashboard_router
from novoya_api.health.presentation.http.router import router as health_router
from novoya_api.planning.presentation.http.router import admin_router as admin_plans_router
from novoya_api.planning.presentation.http.router import agent_router as planning_agent_router
from novoya_api.planning.presentation.http.router import router as planning_router
from novoya_api.quoting.presentation.http.router import admin_router as admin_quotes_router
from novoya_api.quoting.presentation.http.router import agent_quotes_router
from novoya_api.quoting.presentation.http.router import agent_router as quoting_agent_router
from novoya_api.quoting.presentation.http.router import router as quoting_router
from novoya_api.shared.infrastructure.db.session import get_sessionmaker
from novoya_api.shared.presentation.http.errors import register_error_handlers
from novoya_api.shared.presentation.http.origin_middleware import OriginCheckMiddleware
from novoya_api.wishes.presentation.http.router import admin_router as admin_wishes_router
from novoya_api.wishes.presentation.http.router import router as wishes_router

logger = logging.getLogger(__name__)


async def clean_up_sign_ins() -> None:
    """Expired sessions and email links go at startup too, not only at the next sign-in: the
    privacy page promises sessions are kept 30 days at most. A database that does not
    answer yet must not stop the API from starting; the next sign-in cleans up anyway."""
    try:
        async with get_sessionmaker()() as session:
            await delete_expired_sign_ins(session=session)
            await session.commit()
    except Exception as error:
        logger.warning("Deleting expired sessions at startup failed: %s", type(error).__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await clean_up_sign_ins()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Novoya API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(accounts_router)
    app.include_router(catalog_router)
    app.include_router(wishes_router)
    app.include_router(admin_wishes_router)
    app.include_router(planning_router)
    app.include_router(planning_agent_router)
    app.include_router(admin_plans_router)
    app.include_router(quoting_router)
    app.include_router(quoting_agent_router)
    app.include_router(agent_quotes_router)
    app.include_router(admin_quotes_router)
    app.include_router(dashboard_router)
    return app


app = create_app()
