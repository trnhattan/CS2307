from datetime import datetime

from pydantic import BaseModel, Field


class ExplanationPayload(BaseModel):
    explanation: str = Field(min_length=10, max_length=4000)
    evidence_used: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class ExamExplanationResponse(ExplanationPayload):
    artifact_id: int
    session_id: int
    audience: str
    model: str
    cached: bool
    generated_at: datetime
