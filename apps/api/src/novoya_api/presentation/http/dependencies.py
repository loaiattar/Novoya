"""Wiring: build each use case with its infrastructure adapters, as FastAPI dependencies.

This module and main.py are the only places outside infrastructure that may import
infrastructure (the composition root). Tests replace these dependencies with fakes.
Planned here too: current_user and require_agent (403 for clients) (#49).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.application.ports.health import DatabaseProbe
from novoya_api.application.use_cases.check_database import CheckDatabase
from novoya_api.infrastructure.db.probe import SqlDatabaseProbe
from novoya_api.infrastructure.db.session import get_session


def get_database_probe(session: Annotated[AsyncSession, Depends(get_session)]) -> DatabaseProbe:
    return SqlDatabaseProbe(session)


def get_check_database(
    probe: Annotated[DatabaseProbe, Depends(get_database_probe)],
) -> CheckDatabase:
    return CheckDatabase(probe)
