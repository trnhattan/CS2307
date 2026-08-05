from datetime import datetime

from pydantic import BaseModel, Field


class CreateChatThreadRequest(BaseModel):
    subject_code: str | None = Field(default=None, max_length=50)
    title: str = Field(default="Learning assistant", min_length=1, max_length=255)


class ChatThreadSummary(BaseModel):
    thread_id: int
    title: str
    subject_code: str | None
    subject_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    message_id: int
    role: str
    content: str
    intent: str | None
    session_id: int | None
    question_code: str | None = None
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    model: str | None
    used_llm: bool
    created_at: datetime


class ChatThreadDetail(ChatThreadSummary):
    messages: list[ChatMessage]


class DeleteChatThreadResponse(BaseModel):
    thread_id: int
    deleted: bool = True


class SendChatMessageRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    session_id: int | None = Field(default=None, ge=1)
    question_code: str | None = Field(default=None, max_length=80)


class ChatAssistantPayload(BaseModel):
    answer: str = Field(min_length=5, max_length=5000)
    evidence_used: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class SendChatMessageResponse(ChatMessage):
    pass
