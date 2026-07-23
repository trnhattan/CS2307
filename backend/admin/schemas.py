from typing import Any

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
