from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.kb.repository import KnowledgeBaseRepository
from backend.kb.schemas import (
    ClosureRequest,
    ClosureResponse,
    RulePayload,
    RuleValidationResponse,
    StoredTraceResponse,
)
from backend.kb.service import KnowledgeBaseService


router = APIRouter()


def get_kb_service() -> KnowledgeBaseService:
    return KnowledgeBaseService(KnowledgeBaseRepository(), async_session_factory)


@router.post("/closure", response_model=ClosureResponse)
async def closure(
    request: ClosureRequest,
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> ClosureResponse:
    return await get_kb_service().closure(request)


@router.post("/validate-rule", response_model=RuleValidationResponse)
async def validate_rule(
    request: RulePayload,
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> RuleValidationResponse:
    return await get_kb_service().validate_rule(request)


@router.get("/traces/{trace_id}", response_model=StoredTraceResponse)
async def trace(
    trace_id: int,
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> StoredTraceResponse:
    value = await get_kb_service().trace(trace_id)
    if value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return value
