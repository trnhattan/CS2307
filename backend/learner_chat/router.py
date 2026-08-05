from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.core.config import get_settings
from backend.db.session import async_session_factory
from backend.learner_chat.errors import LearnerChatError, LearnerChatNotFoundError
from backend.learner_chat.repository import LearnerChatRepository
from backend.learner_chat.schemas import (
    ChatThreadDetail,
    ChatThreadSummary,
    CreateChatThreadRequest,
    DeleteChatThreadResponse,
    SendChatMessageRequest,
    SendChatMessageResponse,
)
from backend.learner_chat.service import LearnerChatService
from backend.llm.client import create_llm_client


router = APIRouter(prefix="/taker/chat")


def get_chat_service() -> LearnerChatService:
    settings = get_settings()
    return LearnerChatService(
        LearnerChatRepository(),
        async_session_factory,
        settings,
        create_llm_client(settings),
    )


@router.post("/threads", response_model=ChatThreadSummary)
async def create_thread(
    request: CreateChatThreadRequest,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> ChatThreadSummary:
    return await _run(get_chat_service().create_thread(request, user))


@router.get("/threads", response_model=list[ChatThreadSummary])
async def list_threads(
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> list[ChatThreadSummary]:
    return await _run(get_chat_service().threads(user))


@router.get("/threads/{thread_id}", response_model=ChatThreadDetail)
async def thread_detail(
    thread_id: int,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> ChatThreadDetail:
    return await _run(get_chat_service().detail(thread_id, user))


@router.delete(
    "/threads/{thread_id}",
    response_model=DeleteChatThreadResponse,
)
async def delete_thread(
    thread_id: int,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> DeleteChatThreadResponse:
    return await _run(get_chat_service().delete_thread(thread_id, user))


@router.post(
    "/threads/{thread_id}/messages",
    response_model=SendChatMessageResponse,
)
async def send_message(
    thread_id: int,
    request: SendChatMessageRequest,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> SendChatMessageResponse:
    return await _run(get_chat_service().send(thread_id, request, user))


async def _run(awaitable):
    try:
        return await awaitable
    except LearnerChatNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except LearnerChatError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
