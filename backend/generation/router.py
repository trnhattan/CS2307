from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.core.config import get_settings
from backend.db.session import async_session_factory
from backend.generation.errors import (
    GenerationCatalogError,
    GenerationUnavailableError,
)
from backend.generation.repository import QuestionGenerationRepository
from backend.generation.schemas import (
    GeneratedQuestion,
    GenerationCatalog,
    GenerationStatus,
    QuestionGenerationRequest,
    RecentGenerationResponse,
)
from backend.generation.service import QuestionGenerationService
from backend.llm.client import OpenAICompatibleClient


router = APIRouter()


def get_generation_service() -> QuestionGenerationService:
    settings = get_settings()
    return QuestionGenerationService(
        QuestionGenerationRepository(),
        async_session_factory,
        settings,
        OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
    )


@router.get("/status", response_model=GenerationStatus)
async def generation_status(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> GenerationStatus:
    return await get_generation_service().status()


@router.get("/catalog", response_model=GenerationCatalog)
async def generation_catalog(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> GenerationCatalog:
    return await get_generation_service().catalog()


@router.get("/recent", response_model=RecentGenerationResponse)
async def recent_generations(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> RecentGenerationResponse:
    return RecentGenerationResponse(items=await get_generation_service().recent())


@router.post(
    "/questions",
    response_model=GeneratedQuestion,
    status_code=status.HTTP_201_CREATED,
)
async def generate_question(
    request: QuestionGenerationRequest,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> GeneratedQuestion:
    try:
        return await get_generation_service().generate(request, user.username)
    except GenerationCatalogError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GenerationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
