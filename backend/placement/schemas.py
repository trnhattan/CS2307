from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.exams.schemas import GenerateExamResponse


class PlacementStartRequest(BaseModel):
    subject_code: str = Field(min_length=1, max_length=50)

    @field_validator("subject_code")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        return value.strip().upper()


class PlacementSubjectStatus(BaseModel):
    subject_code: str
    subject_name: str
    status: str
    session_id: int | None
    completed_at: datetime | None
    score_percent: float | None


class PlacementStatusResponse(BaseModel):
    subjects: list[PlacementSubjectStatus]


class PlacementStartResponse(GenerateExamResponse):
    pass
