from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth.dependencies import bearer_scheme, get_current_user
from backend.core.config import get_settings
from backend.db.session import async_session_factory
from backend.questions.errors import DatabaseUnavailableError, ImportFileError
from backend.questions.repository import QuestionBundleRepository
from backend.questions.schemas import QuestionImportResponse
from backend.questions.service import QuestionImportService
from backend.questions.validator import get_question_bundle_validator


router = APIRouter()


def get_import_service() -> QuestionImportService:
    return QuestionImportService(
        settings=get_settings(),
        validator=get_question_bundle_validator(),
        repository=QuestionBundleRepository(),
        session_factory=async_session_factory,
    )


@router.post(
    "/import-jsonl",
    response_model=QuestionImportResponse,
    summary="Validate and import question bundles",
)
async def import_question_bundles(
    file: Annotated[UploadFile, File(description="Question bundle JSONL file")],
    dry_run: Annotated[bool, Query(description="Validate without writing")] = False,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> QuestionImportResponse:
    try:
        if not dry_run:
            user = await get_current_user(credentials)
            if user.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only administrators may import question data",
                )
        return await get_import_service().import_jsonl(file, dry_run=dry_run)
    except ImportFileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except DatabaseUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
