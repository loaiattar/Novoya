from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.db import get_session

router = APIRouter(prefix="/health", tags=["health"])


class Health(BaseModel):
    status: Literal["ok", "error"]


@router.get("", operation_id="getHealth")
async def health() -> Health:
    """Liveness: the process is up."""
    return Health(status="ok")


@router.get("/db", operation_id="getDbHealth", responses={503: {"model": Health}})
async def db_health(
    session: Annotated[AsyncSession, Depends(get_session)], response: Response
) -> Health:
    """Readiness: the database answers."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Health(status="error")
    return Health(status="ok")
