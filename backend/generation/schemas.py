from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate"]
DifficultyLabel = Literal["easy", "medium", "hard"]


class GenerationStatus(BaseModel):
    enabled: bool
    configured: bool
    model: str
    provider: str
    one_question_per_request: bool = True
    activation_policy: str = "draft_requires_admin_review"


class CatalogUnit(BaseModel):
    code: str
    name: str
    type: Literal["topic", "skill"]


class CatalogSubject(BaseModel):
    code: str
    name: str
    units: list[CatalogUnit]


class GenerationCatalog(BaseModel):
    subjects: list[CatalogSubject]
    bloom_levels: list[str]
    difficulty_labels: list[str]


class QuestionGenerationRequest(BaseModel):
    subject_code: str = Field(min_length=1, max_length=50)
    topic_code: str = Field(min_length=1, max_length=100)
    skill_codes: list[str] = Field(min_length=1, max_length=5)
    bloom_level: BloomLevel
    difficulty_label: DifficultyLabel
    learning_objective: str | None = Field(default=None, max_length=500)
    source_title: str | None = Field(default=None, max_length=255)
    source_context: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def normalize_codes(self):
        self.subject_code = self.subject_code.strip().upper()
        self.topic_code = self.topic_code.strip().upper()
        self.skill_codes = [value.strip().upper() for value in self.skill_codes]
        if len(self.skill_codes) != len(set(self.skill_codes)):
            raise ValueError("skill_codes must be unique")
        if self.source_context is not None:
            self.source_context = self.source_context.strip() or None
        if self.source_title is not None:
            self.source_title = self.source_title.strip() or None
        return self


class GeneratedOption(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    distractor_type: Literal["near_correct", "misconception", "clear_wrong"] = (
        "clear_wrong"
    )
    diagnosis: str | None = Field(default=None, max_length=1000)


class GeneratedQuestionPayload(BaseModel):
    stem: str = Field(min_length=10, max_length=4000)
    options: list[GeneratedOption] = Field(min_length=2, max_length=10)
    correct_index: int = Field(ge=0, le=9)
    explanation: str = Field(min_length=10, max_length=4000)
    bloom_rationale: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="before")
    @classmethod
    def normalize_correct_option_marker(cls, data):
        if not isinstance(data, dict):
            return data
        options = data.get("options")
        correct_index = data.get("correct_index")
        if not isinstance(options, list) or not isinstance(correct_index, int):
            return data
        if 0 <= correct_index < len(options) and isinstance(options[correct_index], dict):
            marker = options[correct_index].get("distractor_type")
            if marker in {"best", "correct"}:
                normalized = dict(data)
                normalized_options = [dict(option) if isinstance(option, dict) else option for option in options]
                normalized_options[correct_index]["distractor_type"] = "clear_wrong"
                normalized["options"] = normalized_options
                return normalized
        return data

    @model_validator(mode="after")
    def valid_correct_index(self):
        if self.correct_index >= len(self.options):
            raise ValueError("correct_index must reference an option")
        return self


class GenerationValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["blocking", "warning"]


class InitialIRT(BaseModel):
    a: float
    b: float
    c: float
    difficulty_norm: float
    avg_time_sec: int
    rubric_version: str


class GeneratedQuestion(BaseModel):
    artifact_id: int
    question_code: str
    status: Literal["draft"]
    subject_code: str
    topic_code: str
    skill_codes: list[str]
    bloom_level: BloomLevel
    difficulty_label: DifficultyLabel
    stem: str
    options: list[dict[str, Any]]
    correct_option_code: str
    explanation: str
    bloom_rationale: str
    irt: InitialIRT
    validation_issues: list[GenerationValidationIssue]
    model: str


class RecentGeneratedQuestion(BaseModel):
    artifact_id: int
    question_code: str | None
    status: str
    model: str
    subject_code: str | None
    bloom_level: str | None
    difficulty_label: str | None
    created_by: str | None
    created_at: datetime
    error_message: str | None


class RecentGenerationResponse(BaseModel):
    items: list[RecentGeneratedQuestion]
