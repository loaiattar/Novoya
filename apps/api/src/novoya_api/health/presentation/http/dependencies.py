"""Composition root of the health module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.health.application.ports import DatabaseProbe
from novoya_api.health.application.use_cases.check_database import CheckDatabase
from novoya_api.health.infrastructure.sql_probe import SqlDatabaseProbe
from novoya_api.shared.infrastructure.db.session import get_session


def get_database_probe(session: Annotated[AsyncSession, Depends(get_session)]) -> DatabaseProbe:
    return SqlDatabaseProbe(session)


def get_check_database(
    probe: Annotated[DatabaseProbe, Depends(get_database_probe)],
) -> CheckDatabase:
    return CheckDatabase(probe)
