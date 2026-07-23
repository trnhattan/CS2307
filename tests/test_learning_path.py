from backend.takers.service import TakerService


def test_learning_path_prioritizes_weak_units_with_rule_trace() -> None:
    service = TakerService(None, None)  # type: ignore[arg-type]
    evidence = [
        {
            "subject_code": "DATABASE",
            "subject_name": "Cơ sở dữ liệu",
            "unit_code": "SQL_JOIN",
            "unit_name": "SQL Join",
            "unit_type": "skill",
            "evidence_count": 5,
            "accuracy_percent": 40,
        },
        {
            "subject_code": "DATABASE",
            "subject_name": "Cơ sở dữ liệu",
            "unit_code": "SQL_BASIC",
            "unit_name": "SQL cơ bản",
            "unit_type": "skill",
            "evidence_count": 5,
            "accuracy_percent": 80,
        },
    ]

    path = service._build_learning_path(evidence, [])

    assert path[0].unit_code == "SQL_JOIN"
    assert path[0].rule_code == "R_LEARNING_REMEDIATE"
    assert path[1].rule_code == "R_LEARNING_ADVANCE"


def test_learning_path_starts_unassessed_subject() -> None:
    service = TakerService(None, None)  # type: ignore[arg-type]
    progress = [
        {
            "subject_code": "NETWORK",
            "subject_name": "Mạng máy tính",
        }
    ]

    path = service._build_learning_path([], progress)

    assert path[0].rule_code == "R_LEARNING_START_SUBJECT"
    assert path[0].evidence_count == 0
