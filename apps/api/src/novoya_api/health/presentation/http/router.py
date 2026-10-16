from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from novoya_api.health.application.use_cases.check_database import CheckDatabase
from novoya_api.health.presentation.http.dependencies import get_check_database
from novoya_api.health.presentation.http.schemas import Health

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", operation_id="getHealth")
async def health() -> Health:
    """Liveness: the process is up."""
    return Health(status="ok")


@router.get("/db", operation_id="getDbHealth", responses={503: {"model": Health}})
async def db_health(
    check_database: Annotated[CheckDatabase, Depends(get_check_database)], response: Response
) -> Health:
    """Readiness: the database answers."""
    if await check_database():
        return Health(status="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Health(status="error")
