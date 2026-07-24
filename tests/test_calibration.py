from backend.calibration.service import CalibrationService


def _rows(count: int) -> list[dict]:
    return [
        {
            "question_id": 1,
            "question_code": "DB-1",
            "subject_code": "DATABASE",
            "irt_a": 1.2,
            "irt_b": 0.4,
            "irt_c": 0.25,
            "is_correct": index % 3 != 0,
            "theta_before": -1 + 2 * index / max(1, count - 1),
            "response_time_sec": 40 + index,
        }
        for index in range(count)
    ]


def test_calibration_marks_sparse_real_data_as_insufficient() -> None:
    result = CalibrationService._evaluate(_rows(12), 30, 100, 1.7)

    assert result["sample_size"] == 12
    assert result["reliability"] == "insufficient"
    assert result["applied"] is False


def test_calibration_estimates_difficulty_only_from_varied_responses() -> None:
    result = CalibrationService._evaluate(_rows(120), 30, 100, 1.7)

    assert result["reliability"] == "eligible"
    assert -4 <= result["suggested_b"] <= 4
    assert result["point_biserial"] is not None
