from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.exams.errors import ExamError, ExamNotFoundError
from backend.exams.repository import ExamRepository
from backend.exams.schemas import GenerateExamRequest
from backend.exams.service import ExamService
from backend.placement.repository import PlacementRepository
from backend.placement.schemas import (
    PlacementStartRequest,
    PlacementStartResponse,
    PlacementStatusResponse,
)


router = APIRouter(prefix="/placement")


@router.get("/status", response_model=PlacementStatusResponse)
async def placement_status(
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> PlacementStatusResponse:
    if user.student_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    async with async_session_factory() as session:
        rows = await PlacementRepository().status(session, user.student_id)
    return PlacementStatusResponse(subjects=rows)


@router.post("/start", response_model=PlacementStartResponse)
async def start_placement(
    request: PlacementStartRequest,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> PlacementStartResponse:
    service = ExamService(ExamRepository(), async_session_factory)
    try:
        response = await service.generate(
            GenerateExamRequest(
                subject_codes=[request.subject_code],
                assessment_purpose="placement",
            ),
            user,
        )
        return PlacementStartResponse.model_validate(response.model_dump())
    except ExamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ExamError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
