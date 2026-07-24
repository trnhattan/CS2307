import asyncio
import json
from pathlib import Path

import httpx
import pytest

from backend.explanations.service import ExamExplanationService
from backend.explanations.schemas import ExplanationPayload
from backend.generation.rubric import initial_irt
from backend.generation.schemas import GeneratedQuestionPayload, QuestionGenerationRequest
from backend.prompts import load_prompt
from backend.generation.validator import validate_generated_question
from backend.llm.client import OpenAICompatibleClient
from backend.llm.errors import LLMConfigurationError


def test_openai_compatible_client_parses_json_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        return httpx.Response(
            200,
            json={
                "id": "completion-1",
                "model": "test-model",
                "choices": [{"message": {"content": '```json\n{"ok":true}\n```'}}],
                "usage": {"total_tokens": 10},
            },
        )

    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-secret",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    completion = asyncio.run(
        client.complete_json(
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=20,
            temperature=0,
        )
    )

    assert completion.data == {"ok": True}
    assert completion.usage == {"total_tokens": 10}


def test_llm_client_requires_environment_secret() -> None:
    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key=None,
        timeout_seconds=5,
    )
    with pytest.raises(LLMConfigurationError):
        asyncio.run(
            client.complete_json(
                model="test",
                messages=[],
                max_tokens=20,
                temperature=0,
            )
        )


def test_initial_irt_is_deterministic_and_bounded() -> None:
    first = initial_irt("analyze", "hard", 8)
    second = initial_irt("analyze", "hard", 8)

    assert first == second
    assert first.rubric_version == "deterministic-initial-irt-v1"
    assert 0 < first.a <= 1.8
    assert -4 <= first.b <= 4
    assert 0.08 <= first.c <= 0.25


def test_generated_question_validator_blocks_pool_and_near_duplicates() -> None:
    request = QuestionGenerationRequest(
        subject_code="db",
        topic_code="sql",
        skill_codes=["query"],
        bloom_level="analyze",
        difficulty_label="medium",
        source_context="Nguồn kiểm thử",
    )
    generated = GeneratedQuestionPayload(
        stem="Phân tích truy vấn SQL sau để xác định kết quả chính xác.",
        options=[
            {"text": "Kết quả thứ nhất"},
            {"text": "Kết quả thứ hai"},
        ],
        correct_index=0,
        explanation="Giải thích đủ dài dựa trên thứ tự thực thi của truy vấn SQL.",
        bloom_rationale="Yêu cầu phân tích nhiều bước.",
    )
    issues = validate_generated_question(
        generated,
        request,
        expected_option_count=8,
        existing_stems=["Phân tích truy vấn SQL sau để xác định kết quả chính xác!"],
    )

    assert {issue.code for issue in issues} >= {"answer_pool_size", "duplicate_stem"}
    assert all(issue.severity == "blocking" for issue in issues)


def test_taker_explanation_prompt_excludes_staff_metrics() -> None:
    context = {
        "score": {"percentage": 70},
        "unit_evidence": [{"unit": "SQL", "accuracy_percent": 50}],
    }
    messages = ExamExplanationService._messages(context, technical=False)
    system = messages[0]["content"].lower()

    assert "không nhắc theta" in system
    assert "không bịa dữ kiện" in system
    assert "theta" not in messages[1]["content"].lower()


def test_llm_prompts_are_external_and_language_specific() -> None:
    question_prompt = load_prompt("question_generation_system_en.txt")
    explanation_prompt = load_prompt("exam_explanation_system_vi.txt")

    assert "in English" in question_prompt
    assert "tiếng Việt" in explanation_prompt
    assert "{audience_instruction}" in explanation_prompt


def test_correct_option_marker_is_normalized_without_relaxing_distractors() -> None:
    payload = GeneratedQuestionPayload.model_validate(
        {
            "stem": "Which SQL clause filters source rows before grouping occurs?",
            "options": [
                {"text": "WHERE", "distractor_type": "correct"},
                {"text": "HAVING", "distractor_type": "misconception"},
            ],
            "correct_index": 0,
            "explanation": "WHERE filters source rows before GROUP BY evaluates groups.",
            "bloom_rationale": "Recall the SQL processing role.",
        }
    )

    assert payload.options[0].distractor_type == "clear_wrong"


def test_explanation_ownership_parameter_is_typed_for_asyncpg() -> None:
    source = Path("backend/explanations/repository.py").read_text()

    assert "CAST(:student_id AS BIGINT)" in source


def test_xai_evidence_is_grounded_in_deterministic_score_context() -> None:
    context = {
        "score": {
            "earned": 4.0,
            "maximum": 20.0,
            "percentage": 20.0,
            "correct": 4,
            "questions": 20,
        },
        "unit_evidence": [
            {
                "unit": "SQL Querying",
                "accuracy_percent": 25.0,
                "evidence_count": 4,
                "recommendation": "remediate",
            },
            {
                "unit": "Transaction atomicity",
                "accuracy_percent": 100.0,
                "evidence_count": 1,
                "recommendation": "advance",
            },
        ],
    }
    generated = ExplanationPayload(
        explanation="Bạn nên ưu tiên ôn lại SQL cơ bản trước.",
        evidence_used=["Điểm số tổng thể 20/20 (10%)"],
        limitations=[],
    )

    grounded = ExamExplanationService._ground_payload(
        generated, context, technical=False
    )

    assert grounded.evidence_used[0] == (
        "Điểm đã chấm: 4/20 (20.0%); đúng 4/20 câu."
    )
    assert "20/20 (10%)" not in grounded.model_dump_json()


def test_xai_replaces_conflicting_numeric_prose() -> None:
    context = {
        "score": {
            "earned": 4.0,
            "maximum": 20.0,
            "percentage": 20.0,
            "correct": 4,
            "questions": 20,
        },
        "unit_evidence": [],
    }
    generated = ExplanationPayload(
        explanation="Bạn đạt 20/20, tương đương 10%.",
        evidence_used=[],
        limitations=[],
    )

    grounded = ExamExplanationService._ground_payload(
        generated, context, technical=False
    )

    assert grounded.explanation.startswith("Kết quả đã chấm là 4/20 (20.0%).")
    assert any("số liệu không khớp" in value for value in grounded.limitations)


def test_xai_cache_requires_grounding_version() -> None:
    source = Path("backend/explanations/repository.py").read_text()

    assert "deterministic-evidence-v1" in source
