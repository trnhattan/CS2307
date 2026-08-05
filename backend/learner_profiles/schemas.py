from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CriterionDefinition(BaseModel):
    criterion_id: int
    criterion_code: str
    criterion_name: str
    subject_code: str
    subject_name: str
    topic_code: str | None
    topic_name: str | None
    learning_objective: str
    success_statement: str
    mastery_threshold: float
    importance_weight: float
    display_order: int
    mapped_question_count: int


class CriteriaCatalogResponse(BaseModel):
    subject_code: str
    subject_name: str
    criteria: list[CriterionDefinition]


class CriterionState(CriterionDefinition):
    mastery_probability: float | None
    accuracy_percent: float | None
    evidence_count: int
    understanding_label: str
    evidence_confidence: str
    trend: str
    mastery_delta: float | None
    last_assessed_at: datetime | None


class ProfileRecommendation(BaseModel):
    criterion_code: str
    criterion_name: str
    action: str
    reason: str
    priority: int


class SubjectLearnerProfile(BaseModel):
    subject_code: str
    subject_name: str
    criteria: list[CriterionState]
    strengths: list[str]
    weaknesses: list[str]
    improved: list[str]
    regressed: list[str]
    insufficient_evidence: list[str]
    recommendations: list[ProfileRecommendation]


class LearnerProfileResponse(BaseModel):
    student_id: int
    student_code: str
    student_name: str
    subjects: list[SubjectLearnerProfile]


class RadarAxis(BaseModel):
    criterion_code: str
    criterion_name: str
    value_percent: float | None = Field(default=None, ge=0, le=100)
    evidence_count: int
    evidence_confidence: str
    understanding_label: str


class CriterionRadarResponse(BaseModel):
    subject_code: str
    subject_name: str
    scope: Literal["overall", "subject"] = "subject"
    scale_min: int = 0
    scale_max: int = 100
    axes: list[RadarAxis]
    assessed_criteria: int
    total_criteria: int
    note: str
