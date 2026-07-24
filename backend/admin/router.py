from fastapi import APIRouter, Depends, HTTPException, status

from backend.admin.errors import (
    AccountConflictError,
    AccountNotFoundError,
    AdminError,
    QuestionNotFoundError,
    QuestionValidationError,
)
from backend.admin.repository import AdminRepository
from backend.admin.schemas import (
    AccountCreateRequest,
    AccountItem,
    AccountUpdateRequest,
    AdminConfigResponse,
    AdminConfigUpdateResponse,
    BulkQuestionActivationRequest,
    BulkQuestionActivationResponse,
    QuestionBankResponse,
    QuestionDetail,
    QuestionMetadataUpdate,
    QuestionReadinessResponse,
    QuestionReviewResponse,
    SystemOverview,
)
from backend.admin.service import AdminService
from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.system_config.errors import ConfigurationError
from backend.system_config.schemas import ConfigUpdateRequest


router = APIRouter()


def get_admin_service() -> AdminService:
    return AdminService(AdminRepository(), async_session_factory)


@router.get("/overview", response_model=SystemOverview)
async def system_overview(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> SystemOverview:
    return await get_admin_service().overview()


@router.get("/questions", response_model=QuestionBankResponse)
async def question_bank(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> QuestionBankResponse:
    return await get_admin_service().question_bank()


@router.get("/questions/readiness", response_model=QuestionReadinessResponse)
async def question_readiness(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> QuestionReadinessResponse:
    return await get_admin_service().readiness()


@router.post(
    "/questions/bulk-activate",
    response_model=BulkQuestionActivationResponse,
)
async def bulk_activate_questions(
    request: BulkQuestionActivationRequest,
    user: AuthenticatedUser = Depends(require_roles("admin")),
) -> BulkQuestionActivationResponse:
    return await get_admin_service().bulk_activate_questions(
        request.question_codes, user.username
    )


@router.get("/questions/{question_code}", response_model=QuestionDetail)
async def question_detail(
    question_code: str,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> QuestionDetail:
    try:
        return await get_admin_service().question_detail(question_code)
    except QuestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/questions/{question_code}", response_model=QuestionDetail)
async def update_question(
    question_code: str,
    request: QuestionMetadataUpdate,
    user: AuthenticatedUser = Depends(require_roles("admin")),
) -> QuestionDetail:
    try:
        return await get_admin_service().update_question(
            question_code, request, user.username
        )
    except QuestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/questions/{question_code}/review", response_model=QuestionReviewResponse)
async def review_question(
    question_code: str,
    user: AuthenticatedUser = Depends(require_roles("admin")),
) -> QuestionReviewResponse:
    try:
        return await get_admin_service().review_question(question_code, user.username)
    except QuestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/questions/{question_code}/activate", response_model=QuestionReviewResponse)
async def activate_question(
    question_code: str,
    user: AuthenticatedUser = Depends(require_roles("admin")),
) -> QuestionReviewResponse:
    try:
        return await get_admin_service().activate_question(question_code, user.username)
    except QuestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except QuestionValidationError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/config", response_model=AdminConfigResponse)
async def list_config(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> AdminConfigResponse:
    return AdminConfigResponse(items=await get_admin_service().config_items())


@router.put("/config", response_model=AdminConfigUpdateResponse)
async def update_config(
    request: ConfigUpdateRequest,
    user: AuthenticatedUser = Depends(require_roles("admin")),
) -> AdminConfigUpdateResponse:
    try:
        updated = await get_admin_service().update_config(
            [(item.prop_key, item.prop_value) for item in request.updates],
            user.username,
        )
        return AdminConfigUpdateResponse(updated=updated)
    except ConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/accounts", response_model=list[AccountItem])
async def list_accounts(
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> list[AccountItem]:
    return await get_admin_service().accounts()


@router.post(
    "/accounts",
    response_model=AccountItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    request: AccountCreateRequest,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> AccountItem:
    try:
        return await get_admin_service().create_account(request)
    except AccountConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch("/accounts/{username}", response_model=AccountItem)
async def update_account(
    username: str,
    request: AccountUpdateRequest,
    user: AuthenticatedUser = Depends(require_roles("admin")),
) -> AccountItem:
    try:
        return await get_admin_service().update_account(
            username,
            request,
            user.username,
        )
    except AccountNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AdminError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
