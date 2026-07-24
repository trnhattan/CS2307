from datetime import datetime
from typing import Literal

from pydantic import BaseModel


Reliability = Literal["insufficient", "provisional", "eligible"]


class ItemCalibration(BaseModel):
    question_code: str
    subject_code: str
    sample_size: int
    observed_accuracy: float | None
    predicted_accuracy: float | None
    mean_response_time_sec: float | None
    point_biserial: float | None
    fit_rmse: float | None
    current_b: float
    suggested_b: float | None
    reliability: Reliability
    applied: bool


class CalibrationSummary(BaseModel):
    run_id: int
    method: str
    total_responses: int
    evaluated_items: int
    eligible_items: int
    applied_items: int
    minimum_evaluation_sample: int
    minimum_apply_sample: int
    created_by: str
    created_at: datetime
    limitations: list[str]
    items: list[ItemCalibration]


class CalibrationRunRequest(BaseModel):
    apply_eligible: bool = False
