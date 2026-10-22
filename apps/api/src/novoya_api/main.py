from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novoya_api.accounts.presentation.http.router import router as accounts_router
from novoya_api.catalog.presentation.http.router import router as catalog_router
from novoya_api.config import get_settings
from novoya_api.health.presentation.http.router import router as health_router
from novoya_api.planning.presentation.http.router import agent_router as planning_agent_router
from novoya_api.planning.presentation.http.router import router as planning_router
from novoya_api.quoting.presentation.http.router import agent_quotes_router
from novoya_api.quoting.presentation.http.router import agent_router as quoting_agent_router
from novoya_api.quoting.presentation.http.router import router as quoting_router
from novoya_api.shared.presentation.http.errors import register_error_handlers
from novoya_api.shared.presentation.http.origin_middleware import OriginCheckMiddleware
from novoya_api.wishes.presentation.http.router import router as wishes_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Novoya API", version="0.1.0")
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
    app.include_router(planning_router)
    app.include_router(planning_agent_router)
    app.include_router(quoting_router)
    app.include_router(quoting_agent_router)
    app.include_router(agent_quotes_router)
    return app


app = create_app()
