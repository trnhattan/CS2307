import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from backend.explanations.service import ExamExplanationService
from backend.explanations.schemas import ExplanationPayload
from backend.auth.schemas import AuthenticatedUser
from backend.generation.rubric import initial_irt
from backend.generation.schemas import GeneratedQuestionPayload, QuestionGenerationRequest
from backend.prompts import load_prompt
from backend.generation.validator import validate_generated_question
from backend.llm.client import GeminiClient, MultiProviderClient, OpenRouterClient
from backend.llm.errors import LLMConfigurationError, LLMProviderError


def test_openrouter_client_parses_json_completion_and_reasoning() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        assert request.headers["http-referer"] == "https://exam.example"
        assert request.headers["x-openrouter-title"] == "CS2307"
        assert request.url == "https://openrouter.ai/api/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["reasoning"] == {"enabled": True}
        assert "chat_template_kwargs" not in body
        assert body["messages"][1]["reasoning_details"] == [
            {"type": "reasoning.encrypted", "data": "opaque"}
        ]
        return httpx.Response(
            200,
            json={
                "id": "completion-1",
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '```json\n{"ok":true}\n```',
                            "reasoning_details": [
                                {"type": "reasoning.text", "text": "private"}
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 10},
            },
        )

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-secret",
        timeout_seconds=5,
        http_referer="https://exam.example",
        app_title="CS2307",
        transport=httpx.MockTransport(handler),
    )
    completion = asyncio.run(
        client.complete_json(
            model="test-model",
            messages=[
                {"role": "user", "content": "first"},
                {
                    "role": "assistant",
                    "content": '{"ok":false}',
                    "reasoning_details": [
                        {"type": "reasoning.encrypted", "data": "opaque"}
                    ],
                },
                {"role": "user", "content": "test"},
            ],
            max_tokens=20,
            temperature=0,
        )
    )

    assert completion.data == {"ok": True}
    assert completion.usage == {"total_tokens": 10}
    assert completion.reasoning_details == [
        {"type": "reasoning.text", "text": "private"}
    ]


def test_openrouter_client_can_attach_budget_bounded_web_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["tools"] == [
            {
                "type": "openrouter:web_search",
                "max_total_results": 2,
                "search_context_size": "low",
            }
        ]
        return httpx.Response(
            200,
            json={
                "id": "completion-web",
                "model": "test-model",
                "choices": [
                    {"message": {"role": "assistant", "content": '{"ok":true}'}}
                ],
            },
        )

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-secret",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    completion = asyncio.run(
        client.complete_json(
            model="test-model",
            messages=[{"role": "user", "content": "current standard"}],
            max_tokens=20,
            temperature=0,
            web_search_enabled=True,
            web_search_max_results=2,
        )
    )

    assert completion.data == {"ok": True}


def test_openrouter_client_executes_learner_tool_loop() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "id": "tool-request",
                    "model": "test-model",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "search_subject_knowledge",
                                            "arguments": '{"query":"QoS"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                },
            )
        assert body["messages"][-1]["role"] == "tool"
        assert body["messages"][-1]["tool_call_id"] == "call-1"
        assert "Quality of Service" in body["messages"][-1]["content"]
        return httpx.Response(
            200,
            json={
                "id": "tool-answer",
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"answer":"QoS quản lý lưu lượng.","evidence_used":[],"limitations":[]}',
                        }
                    }
                ],
            },
        )

    async def execute(name, arguments):
        assert name == "search_subject_knowledge"
        assert arguments == {"query": "QoS"}
        return {"knowledge": [{"title": "Quality of Service"}]}

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-secret",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    completion = asyncio.run(
        client.complete_json_with_tools(
            model="test-model",
            messages=[{"role": "user", "content": "What is QoS?"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "search_subject_knowledge",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            tool_executor=execute,
            max_tokens=100,
            temperature=0,
        )
    )

    assert completion.data["answer"] == "QoS quản lý lưu lượng."
    assert len(requests) == 2


def test_llm_client_requires_environment_secret() -> None:
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key=None,
        timeout_seconds=5,
    )
    with pytest.raises(LLMConfigurationError, match="OPENROUTER_API_KEY"):
        asyncio.run(
            client.complete_json(
                model="test",
                messages=[],
                max_tokens=20,
                temperature=0,
        )
    )


def test_gemini_client_uses_the_official_openai_compatibility_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer gemini-secret"
        assert request.url == (
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        )
        body = json.loads(request.content)
        assert body["model"] == "gemini-3.1-flash-lite"
        assert body["response_format"] == {"type": "json_object"}
        assert body["google"]["thinking_config"]["thinking_level"] == "low"
        return httpx.Response(
            200,
            json={
                "id": "gemini-completion",
                "model": "gemini-3.1-flash-lite",
                "choices": [
                    {"message": {"role": "assistant", "content": '{"ok":true}'}}
                ],
                "usage": {"total_tokens": 9},
            },
        )

    completion = asyncio.run(
        GeminiClient(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="gemini-secret",
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        ).complete_json(
            model="gemini-3.1-flash-lite",
            messages=[{"role": "user", "content": "Return JSON."}],
            max_tokens=20,
            temperature=0,
        )
    )

    assert completion.data == {"ok": True}
    assert completion.model == "gemini-3.1-flash-lite"


def test_gemini_client_executes_the_existing_learner_tool_contract() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            assert body["tools"][0]["function"]["name"] == "get_my_learning_profile"
            assert body["tool_choice"] == "auto"
            return httpx.Response(
                200,
                json={
                    "id": "gemini-tool-request",
                    "model": "gemini-3.1-flash-lite",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "gemini-call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_my_learning_profile",
                                            "arguments": "{}",
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                },
            )
        assert body["messages"][-1]["role"] == "tool"
        return httpx.Response(
            200,
            json={
                "id": "gemini-tool-answer",
                "model": "gemini-3.1-flash-lite",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"answer":"Bạn đã tiến bộ.","evidence_used":[],"limitations":[]}',
                        }
                    }
                ],
            },
        )

    async def execute(name, arguments):
        assert name == "get_my_learning_profile"
        assert arguments == {}
        return {"subjects": [{"name": "Database Systems"}]}

    completion = asyncio.run(
        GeminiClient(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="gemini-secret",
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        ).complete_json_with_tools(
            model="gemini-3.1-flash-lite",
            messages=[{"role": "user", "content": "What have I learned?"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_my_learning_profile",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            tool_executor=execute,
            max_tokens=100,
            temperature=0,
        )
    )

    assert completion.data["answer"] == "Bạn đã tiến bộ."
    assert len(requests) == 2


def test_multi_provider_selects_gemini_from_the_database_model_name() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_api_key="router-key",
        openrouter_http_referer=None,
        openrouter_app_title=None,
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        gemini_api_key="gemini-key",
        gemini_thinking_level="low",
        llm_timeout_seconds=5,
    )
    client = MultiProviderClient(settings)

    assert client.is_configured("gemini-3.1-flash-lite") is True
    assert client.provider_endpoint("gemini-3.1-flash-lite").endswith("/openai")
    assert client.is_configured("~deepseek/deepseek-v4-flash-latest") is True
    assert client.provider_endpoint("~deepseek/deepseek-v4-flash-latest").endswith("/v1")
    assert client.provider_endpoint(
        "gemini-3.1-flash-lite", "openrouter"
    ).endswith("/v1")
    assert client.provider_endpoint(
        "~deepseek/deepseek-v4-flash-latest", "gemini"
    ).endswith("/openai")


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
    assert "model <> 'deterministic-fallback'" in source


def test_xai_returns_persisted_grounded_fallback_when_provider_rejects_key() -> None:
    context = {
        "score": {
            "earned": 6.0,
            "maximum": 20.0,
            "percentage": 30.0,
            "correct": 6,
            "questions": 20,
        },
        "unit_evidence": [
            {
                "unit": "Table partitioning",
                "accuracy_percent": 25.0,
                "evidence_count": 4,
                "recommendation": "remediate",
            }
        ],
    }

    class Session:
        async def commit(self):
            return None

    class SessionContext:
        async def __aenter__(self):
            return Session()

        async def __aexit__(self, *_):
            return None

    class SessionFactory:
        def __call__(self):
            return SessionContext()

    class Repository:
        saved_model = None
        saved_payload = None

        async def context(self, *_, **__):
            return context

        async def cached(self, *_, **__):
            return None

        async def config(self, *_):
            return {
                "LLM_ENABLED": True,
                "LLM_MODEL": "test-model",
                "LLM_EXPLANATION_MAX_TOKENS": 100,
            }

        async def create_artifact(self, *_, **__):
            return 17

        async def mark_success(self, _, artifact_id, model, payload, usage):
            self.saved_model = model
            self.saved_payload = payload
            assert artifact_id == 17
            assert usage["fallback"] is True
            return {"generated_at": datetime(2026, 8, 4, tzinfo=UTC)}

    class Client:
        async def complete_json(self, **_):
            raise LLMProviderError("OpenRouter returned HTTP 401")

    repository = Repository()
    service = ExamExplanationService(
        repository,
        SessionFactory(),
        SimpleNamespace(openrouter_api_key="rejected-key"),
        Client(),
    )
    user = AuthenticatedUser(
        user_id=1,
        username="taker",
        display_name="Taker",
        role="exam_taker",
        student_id=1,
        student_code="TAKER001",
    )

    response = asyncio.run(
        service.explain(3, user, technical=False, refresh=False)
    )

    assert response.model == "deterministic-fallback"
    assert response.explanation.startswith("Kết quả đã chấm là 6/20 (30.0%).")
    assert repository.saved_model == "deterministic-fallback"
    assert repository.saved_payload["grounding_version"] == (
        "deterministic-evidence-v1"
    )
