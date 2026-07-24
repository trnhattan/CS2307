from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.core.config import get_settings
from backend.db.session import async_session_factory
from backend.explanations.errors import (
    ExplanationNotFoundError,
    ExplanationUnavailableError,
)
from backend.explanations.repository import ExamExplanationRepository
from backend.explanations.schemas import ExamExplanationResponse
from backend.explanations.service import ExamExplanationService
from backend.llm.client import OpenAICompatibleClient


router = APIRouter()


def get_explanation_service() -> ExamExplanationService:
    settings = get_settings()
    return ExamExplanationService(
        ExamExplanationRepository(),
        async_session_factory,
        settings,
        OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
    )


async def _run(
    session_id: int,
    user: AuthenticatedUser,
    *,
    technical: bool,
    refresh: bool,
) -> ExamExplanationResponse:
    try:
        return await get_explanation_service().explain(
            session_id, user, technical=technical, refresh=refresh
        )
    except ExplanationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ExplanationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error


@router.post(
    "/explanations/sessions/{session_id}",
    response_model=ExamExplanationResponse,
)
async def staff_explanation(
    session_id: int,
    refresh: bool = Query(False),
    user: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> ExamExplanationResponse:
    return await _run(session_id, user, technical=True, refresh=refresh)


@router.post(
    "/taker/explanations/{session_id}",
    response_model=ExamExplanationResponse,
)
async def taker_explanation(
    session_id: int,
    refresh: bool = Query(False),
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> ExamExplanationResponse:
    return await _run(session_id, user, technical=False, refresh=refresh)
