from backend.takers.service import TakerService


def test_learning_path_uses_radar_mastery_lowest_first_and_excludes_mastered() -> None:
    service = TakerService(None, None)  # type: ignore[arg-type]
    evidence = [
        {
            "subject_code": "DATABASE",
            "subject_name": "Cơ sở dữ liệu",
            "unit_code": "SQL_JOIN",
            "unit_name": "SQL Join",
            "unit_type": "criterion",
            "evidence_count": 5,
            "mastery_probability": 0.40,
            "mastery_threshold": 0.75,
        },
        {
            "subject_code": "DATABASE",
            "subject_name": "Cơ sở dữ liệu",
            "unit_code": "SQL_BASIC",
            "unit_name": "SQL cơ bản",
            "unit_type": "criterion",
            "evidence_count": 5,
            "mastery_probability": 0.80,
            "mastery_threshold": 0.75,
        },
        {
            "subject_code": "DATABASE",
            "subject_name": "Cơ sở dữ liệu",
            "unit_code": "SQL_WHERE",
            "unit_name": "Apply WHERE clause",
            "unit_type": "criterion",
            "evidence_count": 5,
            "mastery_probability": 0.65,
            "mastery_threshold": 0.75,
        },
    ]

    path = service._build_learning_path(evidence, [])

    assert path[0].unit_code == "SQL_JOIN"
    assert path[0].action == "Review prerequisite knowledge and complete foundational practice"
    assert path[0].mastery_percent == 40
    assert path[1].unit_code == "SQL_WHERE"
    assert path[1].understanding_label == "Understands"
    assert all(step.unit_code != "SQL_BASIC" for step in path)


def test_learning_path_priorities_restart_for_each_subject() -> None:
    service = TakerService(None, None)  # type: ignore[arg-type]
    evidence = [
        {
            "subject_code": code,
            "subject_name": name,
            "unit_code": unit,
            "unit_name": unit,
            "unit_type": "criterion",
            "evidence_count": 4,
            "mastery_probability": mastery,
            "mastery_threshold": 0.75,
        }
        for code, name, unit, mastery in (
            ("DATABASE", "Database Systems", "DB_LOW", 0.2),
            ("DATABASE", "Database Systems", "DB_HIGH", 0.6),
            ("NETWORK", "Computer Networks", "NET_LOW", 0.1),
            ("NETWORK", "Computer Networks", "NET_HIGH", 0.5),
        )
    ]

    path = service._build_learning_path(evidence, [])

    assert [(step.subject_code, step.priority) for step in path] == [
        ("NETWORK", 1),
        ("NETWORK", 2),
        ("DATABASE", 1),
        ("DATABASE", 2),
    ]
    assert [step.mastery_percent for step in path[:2]] == [10, 50]


def test_learning_path_starts_unassessed_subject() -> None:
    service = TakerService(None, None)  # type: ignore[arg-type]
    progress = [
        {
            "subject_code": "NETWORK",
            "subject_name": "Mạng máy tính",
        }
    ]

    path = service._build_learning_path([], progress)

    assert path[0].action == "Complete the first assessment"
    assert path[0].evidence_count == 0
