from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.supervisor.repository import SupervisorRepository
from backend.supervisor.schemas import AdminDashboardResponse, SupervisorDashboardResponse
from backend.supervisor.service import SupervisorService
from backend.system_config.errors import ConfigurationError
from backend.system_config.schemas import (
    CATConfigResponse,
    CATConfigUpdate,
    DifficultyConfigResponse,
    DifficultyDistribution,
)


router = APIRouter()


def get_supervisor_service() -> SupervisorService:
    return SupervisorService(SupervisorRepository(), async_session_factory)


@router.get("/supervisor/dashboard", response_model=SupervisorDashboardResponse)
async def supervisor_dashboard(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> SupervisorDashboardResponse:
    return await get_supervisor_service().dashboard()


@router.get(
    "/supervisor/config/difficulty-distribution",
    response_model=DifficultyConfigResponse,
)
async def get_difficulty_distribution(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> DifficultyConfigResponse:
    return await get_supervisor_service().difficulty_config()


@router.put(
    "/supervisor/config/difficulty-distribution",
    response_model=DifficultyConfigResponse,
)
async def update_difficulty_distribution(
    distribution: DifficultyDistribution,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> DifficultyConfigResponse:
    try:
        return await get_supervisor_service().update_difficulty_config(
            distribution,
            user.username,
        )
    except ConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/supervisor/config/cat", response_model=CATConfigResponse)
async def get_cat_config(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> CATConfigResponse:
    return await get_supervisor_service().cat_config()


@router.put("/supervisor/config/cat", response_model=CATConfigResponse)
async def update_cat_config(
    request: CATConfigUpdate,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> CATConfigResponse:
    try:
        return await get_supervisor_service().update_cat_config(request, user.username)
    except ConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> AdminDashboardResponse:
    return await get_supervisor_service().admin_dashboard()
