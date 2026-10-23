"""Composition root of the dashboard module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.dashboard.application.use_cases.get_admin_stats import GetAdminStats
from novoya_api.dashboard.infrastructure.module_counts import ModuleCounts
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.system_clock import SystemClock


def get_get_admin_stats(session: Annotated[AsyncSession, Depends(get_session)]) -> GetAdminStats:
    return GetAdminStats(counts=ModuleCounts(session), clock=SystemClock())
