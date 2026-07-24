from pydantic import BaseModel, Field, model_validator


class SubjectSummary(BaseModel):
    subject_code: str
    subject_name: str
    description: str | None
    available_questions: int


class ExamRuntimeConfig(BaseModel):
    default_question_count: int
    display_option_count: int
    difficulty_distribution: dict[str, float]
    selection_strategy: str
    irt_model: str


class TakerExamConfig(BaseModel):
    default_question_count: int
    difficulty_distribution: dict[str, float]


class SubjectListResponse(BaseModel):
    subjects: list[SubjectSummary]
    config: TakerExamConfig


class GenerateExamRequest(BaseModel):
    subject_codes: list[str] = Field(min_length=1)
    question_count: int | None = Field(default=None, ge=1, le=100)
    difficulty_distribution: dict[str, float] | None = None
    seed: int | None = None
    topic_codes: list[str] = Field(default_factory=list, max_length=50)
    skill_codes: list[str] = Field(default_factory=list, max_length=50)
    bloom_levels: list[str] = Field(default_factory=list, max_length=5)
    max_estimated_minutes: int | None = Field(default=None, ge=1, le=1440)

    @model_validator(mode="after")
    def validate_subjects_and_distribution(self):
        normalized = [code.strip().upper() for code in self.subject_codes if code.strip()]
        if not normalized:
            raise ValueError("Select at least one subject")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Subject codes must be unique")
        self.subject_codes = normalized
        self.topic_codes = sorted({code.strip().upper() for code in self.topic_codes if code.strip()})
        self.skill_codes = sorted({code.strip().upper() for code in self.skill_codes if code.strip()})
        self.bloom_levels = sorted({value.strip().lower() for value in self.bloom_levels if value.strip()})
        allowed_bloom = {"remember", "understand", "apply", "analyze", "evaluate"}
        invalid_bloom = sorted(set(self.bloom_levels) - allowed_bloom)
        if invalid_bloom:
            raise ValueError(f"Unsupported Bloom levels: {', '.join(invalid_bloom)}")

        if self.difficulty_distribution is not None:
            expected = {"easy", "medium", "hard"}
            if set(self.difficulty_distribution) != expected:
                raise ValueError("Difficulty distribution requires easy, medium, and hard")
            if any(value < 0 for value in self.difficulty_distribution.values()):
                raise ValueError("Difficulty weights cannot be negative")
            total = sum(self.difficulty_distribution.values())
            if total <= 0:
                raise ValueError("Difficulty weights must have a positive sum")
            self.difficulty_distribution = {
                key: value / total for key, value in self.difficulty_distribution.items()
            }
        return self


class ExamOption(BaseModel):
    option_code: str
    option_text: str


class ExamQuestion(BaseModel):
    exam_item_id: int
    order_no: int
    question_code: str
    stem: str
    options: list[ExamOption]


class GeneratedSession(BaseModel):
    session_id: int
    subject_code: str
    subject_name: str
    question_count: int
    estimated_minutes: int
    questions: list[ExamQuestion]


class GenerateExamResponse(BaseModel):
    student_code: str
    sessions: list[GeneratedSession]


class AnswerSubmission(BaseModel):
    exam_item_id: int
    selected_option_code: str
    response_time_sec: int = Field(default=0, ge=0, le=86400)


class SubmitExamRequest(BaseModel):
    answers: list[AnswerSubmission] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_items(self):
        item_ids = [answer.exam_item_id for answer in self.answers]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Each exam item can only be answered once")
        return self


class AnswerFeedback(BaseModel):
    exam_item_id: int
    question_code: str
    stem: str
    selected_option_code: str
    selected_option_text: str
    correct_option_code: str
    correct_option_text: str
    is_correct: bool
    awarded_score: float
    explanation: str | None


class SubmitExamResponse(BaseModel):
    session_id: int
    subject_code: str
    total_score: float
    max_score: float
    percentage: float
    understanding_label: str
    feedback: list[AnswerFeedback]
