from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_sessions: int
    completed_sessions: int
    in_progress_sessions: int
    exam_takers: int
    average_score_percent: float


class SessionAnalytics(BaseModel):
    session_id: int
    student_code: str
    student_name: str
    subject_code: str
    subject_name: str
    status: str
    mode: str
    question_count: int
    answered_count: int
    total_score: float
    max_score: float
    score_percent: float
    theta_initial: float
    theta_current: float
    standard_error: float
    average_item_information: float
    difficulty_distribution: dict[str, int]
    bloom_distribution: dict[str, int]
    generation_config: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None


class AbilityAnalytics(BaseModel):
    student_code: str
    student_name: str
    subject_code: str
    subject_name: str
    theta: float
    standard_error: float
    mastery_probability: float | None
    evidence_count: int
    updated_at: datetime


class TakerOverview(BaseModel):
    student_id: int
    username: str
    student_code: str
    student_name: str
    completed_tests: int
    subjects_assessed: int
    average_score_percent: float
    best_score_percent: float
    latest_score_percent: float | None
    average_theta: float | None
    average_mastery_probability: float | None
    latest_test_at: datetime | None


class SupervisorDashboardResponse(BaseModel):
    summary: DashboardSummary
    takers: list[TakerOverview]
    sessions: list[SessionAnalytics]
    abilities: list[AbilityAnalytics]


class AccountSummary(BaseModel):
    username: str
    display_name: str
    role: str
    student_code: str | None
    is_active: bool


class AdminDashboardResponse(BaseModel):
    assessment: SupervisorDashboardResponse
    accounts: list[AccountSummary]
    system_config: dict[str, Any]
