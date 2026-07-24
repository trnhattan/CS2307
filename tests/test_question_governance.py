from backend.admin.service import AdminService


def valid_question() -> dict:
    return {
        "is_pool_valid": True,
        "explanation": "Giải thích",
        "source": "manual",
        "topic_count": 1,
        "primary_skill_count": 1,
        "duplicate_stem": False,
        "difficulty_norm": 0.55,
        "difficulty_label": "medium",
        "bloom_level": "apply",
        "provenance": {"source": "existing_bank"},
        "irt_a": 1.2,
        "irt_b": 0.0,
        "irt_c": 0.2,
        "invalid_option_count": 0,
    }


def test_valid_question_has_no_blocking_issues() -> None:
    issues = AdminService._validation_issues(valid_question())
    assert not [issue for issue in issues if issue.severity == "blocking"]


def test_activation_validator_detects_deterministic_blockers() -> None:
    question = valid_question()
    question.update(
        {
            "is_pool_valid": False,
            "explanation": "",
            "source": None,
            "topic_count": 0,
            "primary_skill_count": 0,
            "duplicate_stem": True,
            "difficulty_norm": 0.9,
        }
    )
    issues = AdminService._validation_issues(question)
    codes = {issue.code for issue in issues if issue.severity == "blocking"}
    assert {
        "invalid_answer_pool",
        "missing_explanation",
        "missing_source",
        "invalid_topic",
        "invalid_primary_skill",
        "duplicate_stem",
        "difficulty_mismatch",
    }.issubset(codes)
