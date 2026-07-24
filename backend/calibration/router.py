from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.calibration.repository import CalibrationRepository
from backend.calibration.schemas import CalibrationRunRequest, CalibrationSummary
from backend.calibration.service import CalibrationService
from backend.db.session import async_session_factory


router = APIRouter()


def get_service() -> CalibrationService:
    return CalibrationService(CalibrationRepository(), async_session_factory)


@router.post("/run", response_model=CalibrationSummary)
async def run_calibration(
    request: CalibrationRunRequest,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> CalibrationSummary:
    return await get_service().run(user.username, request.apply_eligible)


@router.get("/latest", response_model=CalibrationSummary)
async def latest_calibration(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> CalibrationSummary:
    result = await get_service().latest()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No empirical calibration run is available",
        )
    return result
