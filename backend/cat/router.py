from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.cat.repository import CATRepository
from backend.cat.schemas import (
    CATAnswerRequest,
    CATAnswerResponse,
    CATPublicResult,
    CATStaffDetail,
    CATStartRequest,
    CATStartResponse,
)
from backend.cat.service import CATService
from backend.db.session import async_session_factory
from backend.exams.errors import ExamError, ExamNotFoundError, ExamStateError


router = APIRouter()


def get_cat_service() -> CATService:
    return CATService(CATRepository(), async_session_factory)


def raise_exam_error(error: ExamError) -> None:
    if isinstance(error, ExamNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ExamStateError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=str(error)) from error


@router.post("/start", response_model=CATStartResponse)
async def start(
    request: CATStartRequest,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> CATStartResponse:
    try:
        return await get_cat_service().start(request, user)
    except ExamError as error:
        raise_exam_error(error)


@router.post("/{session_id}/answer", response_model=CATAnswerResponse)
async def answer(
    session_id: int,
    request: CATAnswerRequest,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> CATAnswerResponse:
    try:
        return await get_cat_service().answer(session_id, request, user)
    except ExamError as error:
        raise_exam_error(error)


@router.get("/{session_id}/result", response_model=CATPublicResult)
async def result(
    session_id: int,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> CATPublicResult:
    try:
        return await get_cat_service().result(session_id, user)
    except ExamError as error:
        raise_exam_error(error)


staff_router = APIRouter()


@staff_router.get("/supervisor/cat/{session_id}", response_model=CATStaffDetail)
async def staff_detail(
    session_id: int,
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> CATStaffDetail:
    try:
        return await get_cat_service().staff_detail(session_id)
    except ExamError as error:
        raise_exam_error(error)
