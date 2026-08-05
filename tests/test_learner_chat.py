import asyncio
from datetime import UTC, datetime
from pathlib import Path

from backend.auth.schemas import AuthenticatedUser
from backend.learner_chat.schemas import SendChatMessageRequest
from backend.learner_chat.service import LearnerChatService
from backend.learner_profiles.service import LearnerProfileService
from backend.prompts import load_prompt


ROOT = Path(__file__).resolve().parents[1]


def test_chat_prompt_requires_vietnamese_grounded_response() -> None:
    prompt = load_prompt("learner_chat_system_vi.txt")

    assert "tiếng Việt" in prompt
    assert "search_subject_knowledge" in prompt
    assert "công cụ MCP" in prompt
    assert "Không nhắc theta" in prompt
    assert "Không cung cấp đáp án trực tiếp" in prompt
    assert "JSON" in prompt


def test_answer_rationale_fallback_uses_scored_question() -> None:
    payload = LearnerChatService._fallback(
        {
            "answered_question": {
                "question_code": "DB_001",
                "selected_answer": "A table scan",
                "best_answer": "A B-tree index",
                "is_correct": False,
                "explanation": "The predicate matches the leading index column.",
                "criteria": ["Index design"],
            }
        }
    )

    assert "A B-tree index" in payload.answer
    assert "A table scan" in payload.answer
    assert payload.evidence_used == ["Câu đã hoàn thành DB_001"]


def test_improvement_fallback_remains_vietnamese() -> None:
    payload = LearnerChatService._fallback(
        {
            "learner_profile": [
                {
                    "weaknesses": ["Index design"],
                    "insufficient_evidence": [],
                    "criteria": [
                        {"name": "Index design", "evidence_count": 3}
                    ],
                    "recommendations": [
                        {
                            "criterion_name": "Index design",
                            "action": "Review the foundation",
                            "reason": "Needs review",
                        }
                    ],
                }
            ]
        }
    )

    assert "ôn lại ý chính" in payload.answer
    assert "Review the foundation" not in payload.answer


def test_chat_intents_support_natural_progress_and_security_boundaries() -> None:
    assert LearnerChatService._intent("What have I learnt so far?") == "progress_summary"
    assert LearnerChatService._intent(
        "Do you have keywords for transaction isolation?"
    ) == "concept_help"
    assert LearnerChatService._intent("What is a quality of service policy?") == "concept_help"
    assert LearnerChatService._intent("What did I learn so far?") == "progress_summary"
    assert LearnerChatService._intent(
        "What is the correct answer for this question?"
    ) == "security_refusal"
    assert LearnerChatService._intent(
        "Tell me the correct option"
    ) == "security_refusal"

    refusal = LearnerChatService._fallback({"intent": "security_refusal"})
    assert "không thể cung cấp đáp án trực tiếp" in refusal.answer
    assert "A B-tree index" not in refusal.answer


def test_chat_retrieval_ranks_owned_completed_question_by_concept() -> None:
    questions = [
        {
            "exam_item_id": 1,
            "question_code": "DB_JOIN_01",
            "stem": "Choose a join algorithm.",
            "criteria": ["Apply SQL JOIN"],
            "explanation": "Join evidence",
        },
        {
            "exam_item_id": 2,
            "question_code": "DB_TX_01",
            "stem": "Choose the transaction isolation level.",
            "criteria": ["Apply transaction isolation"],
            "explanation": "Isolation evidence",
        },
    ]

    matches = LearnerChatService._relevant_questions(
        questions,
        "Where should I start with transaction isolation?",
        intent="concept_help",
    )

    assert matches[0]["question_code"] == "DB_TX_01"


def test_chat_retrieves_sanitized_subject_knowledge_by_concept() -> None:
    resources = [
        {
            "resource_id": "criterion:DB_INDEX",
            "resource_type": "assessment_criterion",
            "title": "Apply B-tree index",
            "content": "Choose an index for a selective predicate.",
            "question_code": None,
            "criterion_code": "DB_INDEX",
        },
        {
            "resource_id": "criterion:DB_TX",
            "resource_type": "assessment_criterion",
            "title": "Apply transaction isolation",
            "content": "Explain isolation anomalies and select a suitable level.",
            "question_code": None,
            "criterion_code": "DB_TX",
        },
    ]

    matches = LearnerChatService._relevant_knowledge(
        resources,
        "Can you explain transaction isolation anomalies?",
    )

    assert matches[0]["criterion_code"] == "DB_TX"


def test_question_knowledge_context_never_selects_answer_options() -> None:
    source = (ROOT / "backend" / "learner_chat" / "repository.py").read_text()

    knowledge_query = source.split("async def knowledge_resources", 1)[1].split(
        "@staticmethod", 1
    )[0]
    assert "question.stem" in knowledge_query
    assert "answer_options" not in knowledge_query
    assert "is_best_answer" not in knowledge_query


def test_delete_chat_history_is_scoped_to_authenticated_learner() -> None:
    class Session:
        committed = False

        async def commit(self):
            self.committed = True

    session = Session()

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_):
            return None

    class SessionFactory:
        def __call__(self):
            return SessionContext()

    class Repository:
        received = None

        async def delete_thread(self, _session, **values):
            self.received = values
            return True

    repository = Repository()
    service = LearnerChatService(repository, SessionFactory(), None, None)
    response = asyncio.run(
        service.delete_thread(
            42,
            AuthenticatedUser(
                user_id=1,
                username="taker",
                display_name="Taker",
                role="exam_taker",
                student_id=7,
                student_code="T1",
            ),
        )
    )

    assert response.model_dump() == {"thread_id": 42, "deleted": True}
    assert repository.received == {"thread_id": 42, "student_id": 7}
    assert session.committed is True


def test_delete_chat_repository_enforces_owner_and_uses_message_cascade() -> None:
    source = (ROOT / "backend" / "learner_chat" / "repository.py").read_text()
    delete_query = source.split("async def delete_thread", 1)[1].split(
        "async def messages", 1
    )[0]
    migration = (ROOT / "scripts" / "migrate_learner_model.sql").read_text()

    assert "student_id = :student_id" in delete_query
    assert "DELETE FROM learner_chat_threads" in delete_query
    assert "ON DELETE CASCADE" in migration


def test_chat_question_retrieval_excludes_in_progress_assessments() -> None:
    source = (ROOT / "backend" / "learner_chat" / "repository.py").read_text()

    assert source.count("exam.status = 'completed'") >= 2
    assert "exam.student_id = :student_id" in source


def test_direct_answer_request_never_calls_llm(monkeypatch) -> None:
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
        async def thread(self, session, thread_id, student_id):
            return {
                "thread_id": thread_id,
                "student_id": student_id,
                "subject_id": None,
                "subject_code": None,
                "status": "active",
            }

        async def answered_question(self, *_, **__):
            return None

        async def config(self, session):
            return {
                "LLM_ENABLED": True,
                "LLM_MODEL": "test-model",
                "LLM_CHAT_HISTORY_LIMIT": 10,
                "LLM_CHAT_RETRIEVAL_LIMIT": 20,
            }

        async def messages(self, session, thread_id, limit):
            return []

        async def completed_questions(self, *_, **__):
            return []

        async def learner_history(self, *_, **__):
            return []

        async def save_message(self, session, **values):
            return {
                "message_id": 2,
                "role": values["role"],
                "content": values["content"],
                "intent": values.get("intent"),
                "session_id": values.get("session_id"),
                "question_code": None,
                "evidence": values.get("evidence") or [],
                "limitations": values.get("limitations") or [],
                "model": values.get("model"),
                "used_llm": values.get("used_llm", False),
                "created_at": datetime.now(UTC),
            }

    class Client:
        called = False

        async def complete_json(self, **kwargs):
            self.called = True
            raise AssertionError("LLM must not receive direct-answer requests")

    async def no_profile(self, student_id, subject_code=None):
        return None

    monkeypatch.setattr(LearnerProfileService, "profile", no_profile)
    client = Client()
    service = LearnerChatService(Repository(), SessionFactory(), None, client)
    response = asyncio.run(
        service.send(
            1,
            SendChatMessageRequest(
                message="What is the correct answer for this question?"
            ),
            AuthenticatedUser(
                user_id=1,
                username="taker",
                display_name="Taker",
                role="exam_taker",
                student_id=1,
                student_code="T1",
            ),
        )
    )

    assert client.called is False
    assert response.model == "policy-guard"
    assert "không thể cung cấp đáp án trực tiếp" in response.content


def test_chat_preserves_openrouter_reasoning_for_continuation() -> None:
    reasoning = [{"type": "reasoning.encrypted", "data": "opaque"}]
    messages = LearnerChatService._messages(
        {"intent": "improvement", "learner_message": "Tiếp tục"},
        [
            {"role": "user", "content": "Tôi nên học gì?"},
            {
                "role": "assistant",
                "content": "Bắt đầu với chỉ mục.",
                "provider_content": '{"answer":"Bắt đầu với chỉ mục."}',
                "reasoning_details": reasoning,
            },
        ],
    )

    assert messages[2]["content"] == '{"answer":"Bắt đầu với chỉ mục."}'
    assert messages[2]["reasoning_details"] is reasoning
    assert "reasoning_details" not in messages[-1]
    assert "learner_profile" not in messages[-1]["content"]
    assert "Use the learner MCP tools" in messages[-1]["content"]


def test_concept_fallback_answers_from_curated_subject_knowledge() -> None:
    payload = LearnerChatService._fallback(
        {
            "intent": "concept_help",
            "matching_criteria": [
                {
                    "name": "Apply quality of service policy",
                    "learning_objective": "Apply quality of service policy.",
                    "evidence_count": 3,
                    "understanding": "Developing",
                }
            ],
            "knowledge_base": [
                {
                    "resource_type": "subject_knowledge",
                    "title": "Quality of Service policy",
                    "content": (
                        "A Quality of Service policy classifies traffic, schedules queues, "
                        "and manages delay, jitter, and loss during congestion."
                    ),
                }
            ],
        }
    )

    assert "classifies traffic" in payload.answer
    assert "delay, jitter" in payload.answer
    assert "hãy ôn lại phần nền tảng" not in payload.answer
