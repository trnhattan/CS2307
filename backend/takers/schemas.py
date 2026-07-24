from datetime import datetime

from pydantic import BaseModel


class TakerProgressSummary(BaseModel):
    total_tests: int
    completed_tests: int
    average_score_percent: float
    best_score_percent: float


class SubjectProgress(BaseModel):
    subject_code: str
    subject_name: str
    completed_tests: int
    average_score_percent: float
    best_score_percent: float
    latest_score_percent: float | None
    understanding_label: str


class TestHistoryItem(BaseModel):
    session_id: int
    subject_code: str
    subject_name: str
    score_percent: float
    understanding_label: str
    finished_at: datetime


class LearningPathStep(BaseModel):
    priority: int
    subject_code: str
    subject_name: str
    unit_code: str | None
    unit_name: str
    unit_type: str
    accuracy_percent: float | None
    evidence_count: int
    action: str
    explanation: str


class TakerDashboardResponse(BaseModel):
    summary: TakerProgressSummary
    subject_progress: list[SubjectProgress]
    recent_tests: list[TestHistoryItem]
    learning_path: list[LearningPathStep]
