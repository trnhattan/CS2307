from backend.exams.schemas import GenerateExamResponse
from backend.exams.selection import QuestionCandidate, select_fixed_exam
from backend.placement.schemas import PlacementStartResponse


def candidate(code: str, skill: str) -> QuestionCandidate:
    return QuestionCandidate(
        question_id=len(code),
        question_code=code,
        difficulty_label="medium",
        bloom_level="apply",
        topic_name="Indexing",
        topic_code="INDEX",
        skill_codes=(skill,),
        irt_a=1,
        irt_b=0,
        irt_c=0.2,
        avg_time_sec=60,
    )


def test_placement_selection_prioritizes_distinct_criteria() -> None:
    selected = select_fixed_exam(
        [
            candidate("A1", "PRIMARY_KEY"),
            candidate("A2", "PRIMARY_KEY"),
            candidate("B1", "INDEX"),
        ],
        count=2,
        theta=0,
        distribution={"easy": 0, "medium": 1, "hard": 0},
        seed=7,
        prioritize_skill_coverage=True,
    )

    assert len(selected) == 2
    assert {item.candidate.skill_codes[0] for item in selected} == {
        "PRIMARY_KEY",
        "INDEX",
    }
    assert all("criterion coverage" in item.reason for item in selected)


def test_placement_response_accepts_generated_exam_payload() -> None:
    generated = GenerateExamResponse(student_code="TAKER001", sessions=[])

    response = PlacementStartResponse.model_validate(generated.model_dump())

    assert response.student_code == "TAKER001"
