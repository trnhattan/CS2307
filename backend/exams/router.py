from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_current_user, require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.exams.errors import ExamError, ExamNotFoundError, ExamStateError
from backend.exams.repository import ExamRepository
from backend.exams.schemas import (
    GenerateExamRequest,
    GenerateExamResponse,
    SubjectListResponse,
    SubmitExamRequest,
    SubmitExamResponse,
)
from backend.exams.service import ExamService


router = APIRouter()


def get_exam_service() -> ExamService:
    return ExamService(ExamRepository(), async_session_factory)


@router.get("/subjects", response_model=SubjectListResponse)
async def list_subjects(
    _: AuthenticatedUser = Depends(get_current_user),
) -> SubjectListResponse:
    return await get_exam_service().list_subjects()


@router.post("/generate", response_model=GenerateExamResponse)
async def generate_exam(
    request: GenerateExamRequest,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> GenerateExamResponse:
    try:
        return await get_exam_service().generate(request, user)
    except ExamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ExamError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{session_id}/submit", response_model=SubmitExamResponse)
async def submit_exam(
    session_id: int,
    request: SubmitExamRequest,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> SubmitExamResponse:
    try:
        return await get_exam_service().submit(session_id, request, user)
    except ExamNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ExamStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ExamError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
