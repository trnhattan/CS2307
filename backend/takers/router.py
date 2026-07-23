from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.exams.errors import ExamError
from backend.takers.repository import TakerRepository
from backend.takers.schemas import TakerDashboardResponse
from backend.takers.service import TakerService


router = APIRouter()


def get_taker_service() -> TakerService:
    return TakerService(TakerRepository(), async_session_factory)


@router.get("/dashboard", response_model=TakerDashboardResponse)
async def taker_dashboard(
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> TakerDashboardResponse:
    try:
        return await get_taker_service().dashboard(user)
    except ExamError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
