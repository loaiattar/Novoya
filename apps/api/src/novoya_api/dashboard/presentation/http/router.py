from typing import Annotated

from fastapi import APIRouter, Depends

from novoya_api.accounts.public import require_admin
from novoya_api.dashboard.application.use_cases.get_admin_stats import GetAdminStats
from novoya_api.dashboard.presentation.http.dependencies import get_get_admin_stats
from novoya_api.dashboard.presentation.http.schemas import AdminStatsResponse
from novoya_api.shared.presentation.http.errors import ErrorResponse

router = APIRouter(
    prefix="/admin/stats",
    tags=["admin"],
    responses={status_code: {"model": ErrorResponse} for status_code in (401, 403)},
    dependencies=[Depends(require_admin)],
)


@router.get("", operation_id="getAdminStats")
async def get_admin_stats(
    use_case: Annotated[GetAdminStats, Depends(get_get_admin_stats)],
) -> AdminStatsResponse:
    """The key numbers of the agency in one request: partners, offers and extras (active,
    hidden, inactive), reviews, accounts by role, plans and quotes by status. Admin only."""
    return AdminStatsResponse.of(await use_case())
