from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.exams.schemas import ExamOption


class CATStartRequest(BaseModel):
    subject_code: str = Field(min_length=1, max_length=50)

    @field_validator("subject_code")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        return value.strip().upper()


class CATQuestion(BaseModel):
    exam_item_id: int
    order_no: int
    question_code: str
    stem: str
    options: list[ExamOption]


class CATProgress(BaseModel):
    answered: int
    minimum: int
    maximum: int


class CATStartResponse(BaseModel):
    session_id: int
    subject_code: str
    subject_name: str
    estimated_minutes: int
    progress: CATProgress
    question: CATQuestion


class CATAnswerRequest(BaseModel):
    exam_item_id: int
    selected_option_code: str = Field(min_length=1, max_length=20)
    response_time_sec: int = Field(default=0, ge=0, le=86400)


class CATPublicResult(BaseModel):
    session_id: int
    subject_code: str
    subject_name: str
    total_score: float
    max_score: float
    percentage: float
    understanding_label: str
    answered_count: int


class CATAnswerResponse(BaseModel):
    session_id: int
    completed: bool
    progress: CATProgress
    question: CATQuestion | None = None
    result: CATPublicResult | None = None


class CATStaffItem(BaseModel):
    order_no: int
    question_code: str
    is_correct: bool | None
    theta_before: float
    theta_after: float | None
    standard_error_after: float | None
    item_information: float
    selection_reason: str
    scoring_detail: dict[str, Any]


class CATStaffDetail(BaseModel):
    session_id: int
    student_code: str
    student_name: str
    subject_code: str
    subject_name: str
    status: str
    theta_initial: float
    theta_current: float
    standard_error: float
    generation_config: dict[str, Any]
    items: list[CATStaffItem]
