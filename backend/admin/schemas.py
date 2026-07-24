from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.auth.schemas import Role
from backend.system_config.schemas import ConfigItem


class SystemOverview(BaseModel):
    subjects: int
    questions: int
    active_questions: int
    knowledge_units: int
    knowledge_facts: int
    knowledge_rules: int
    users: int
    question_bank_target: int
    question_bank_completion_percent: float


class QuestionBankSubject(BaseModel):
    subject_code: str
    subject_name: str
    total_questions: int
    difficulty_distribution: dict[str, int]
    bloom_distribution: dict[str, int]
    status_distribution: dict[str, int]


class QuestionBankItem(BaseModel):
    question_code: str
    subject_code: str
    subject_name: str
    stem: str
    bloom_level: str
    difficulty_label: str
    status: str
    irt_status: str
    option_count: int
    knowledge_units: list[str]


class QuestionBankResponse(BaseModel):
    total_questions: int
    subjects: list[QuestionBankSubject]
    questions: list[QuestionBankItem]


class AccountItem(BaseModel):
    username: str
    display_name: str
    role: Role
    student_code: str | None
    is_active: bool


class AccountCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=4, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    role: Role
    student_code: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_student_link(self):
        if self.role == "exam_taker" and not self.student_code:
            raise ValueError("Exam taker accounts require a student code")
        if self.role != "exam_taker" and self.student_code:
            raise ValueError("Only exam taker accounts may have a student code")
        return self


class AccountUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=4, max_length=255)
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.display_name is None and self.password is None and self.is_active is None:
            raise ValueError("Provide at least one account change")
        return self


class AdminConfigResponse(BaseModel):
    items: list[ConfigItem]


class AdminConfigUpdateResponse(BaseModel):
    updated: list[ConfigItem]


class QuestionValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["blocking", "warning"]


class QuestionReviewResponse(BaseModel):
    question_code: str
    valid: bool
    status: str
    issues: list[QuestionValidationIssue]
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class QuestionOptionDetail(BaseModel):
    option_code: str
    option_text: str
    score_weight: float
    is_best_answer: bool
    is_active: bool


class QuestionUnitDetail(BaseModel):
    unit_code: str
    unit_name: str
    unit_type: str
    unit_role: str
    measurement_weight: float


class QuestionDetail(BaseModel):
    question_code: str
    subject_code: str
    stem: str
    bloom_level: str
    difficulty_label: str
    difficulty_norm: float
    avg_time_sec: int
    explanation: str | None
    irt_a: float
    irt_b: float
    irt_c: float
    irt_status: str
    status: str
    source: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    provenance: dict[str, Any]
    options: list[QuestionOptionDetail]
    knowledge_units: list[QuestionUnitDetail]


class QuestionMetadataUpdate(BaseModel):
    stem: str | None = Field(default=None, min_length=1)
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate"] | None = None
    difficulty_label: Literal["easy", "medium", "hard"] | None = None
    difficulty_norm: float | None = Field(default=None, ge=0, le=1)
    avg_time_sec: int | None = Field(default=None, ge=1)
    explanation: str | None = Field(default=None, min_length=1)
    irt_a: float | None = Field(default=None, gt=0)
    irt_b: float | None = Field(default=None, ge=-4, le=4)
    irt_c: float | None = Field(default=None, ge=0, le=0.5)
    irt_status: Literal["draft", "estimated", "calibrated", "retired"] | None = None
    source: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one metadata change")
        return self


class SubjectReadiness(BaseModel):
    subject_code: str
    total_questions: int
    active_questions: int
    topic_count: int
    bloom_coverage: int
    difficulty_coverage: int
    cat_minimum: int
    cat_feasible: bool


class QuestionReadinessResponse(BaseModel):
    total_questions: int
    active_questions: int
    target_questions: int
    target_gap: int
    invalid_questions: int
    subjects: list[SubjectReadiness]
    limitations: list[str]


class BulkQuestionActivationRequest(BaseModel):
    question_codes: list[str] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_codes(self):
        normalized = [code.strip() for code in self.question_codes if code.strip()]
        if not normalized:
            raise ValueError("Provide at least one question code")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Question codes must be unique")
        self.question_codes = normalized
        return self


class BulkQuestionActivationResponse(BaseModel):
    activated: list[str]
    rejected: dict[str, list[QuestionValidationIssue]]
