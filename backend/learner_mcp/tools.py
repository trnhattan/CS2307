import re
import unicodedata
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.learner_chat.repository import LearnerChatRepository
from backend.learner_profiles.repository import LearnerProfileRepository
from backend.learner_profiles.service import LearnerProfileService


def learner_tool_definitions() -> list[dict[str, Any]]:
    return [
        _tool(
            "get_my_learning_profile",
            "Get the signed-in learner's criterion mastery, strengths, weaknesses, trends, and recommendations. Use this for progress and what-to-learn questions.",
            {
                "subject_code": {
                    "type": ["string", "null"],
                    "description": "Optional subject code. Omit to inspect all subjects.",
                }
            },
        ),
        _tool(
            "get_my_test_history",
            "Get the signed-in learner's completed-test summary by subject, including latest and average scores.",
            {
                "subject_code": {
                    "type": ["string", "null"],
                    "description": "Optional subject code.",
                }
            },
        ),
        _tool(
            "search_my_completed_questions",
            "Search only questions answered by the signed-in learner in completed tests. Returns their selected answer, scored answer, explanation, result, and measured criteria.",
            {
                "query": {
                    "type": "string",
                    "description": "Question code, wording, concept, criterion, or error to find.",
                },
                "subject_code": {
                    "type": ["string", "null"],
                    "description": "Optional subject code.",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            required=["query"],
        ),
        _tool(
            "review_my_completed_question",
            "Retrieve one completed question owned by the signed-in learner for a safe answer rationale. Never retrieves an in-progress or unseen question.",
            {
                "question_code": {
                    "type": "string",
                    "description": "Question code from the learner's completed history.",
                }
            },
            required=["question_code"],
        ),
        _tool(
            "search_subject_knowledge",
            "Search the system knowledge base for subject concepts, topics, assessment criteria, learning objectives, and sanitized question metadata. Use this before explaining a technical concept.",
            {
                "query": {
                    "type": "string",
                    "description": "Concept or subject question to research, for example quality of service policy.",
                },
                "subject_code": {
                    "type": ["string", "null"],
                    "description": "Optional subject code.",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            required=["query"],
        ),
    ]


class LearnerToolset:
    _STOP_WORDS = {
        "a", "an", "and", "apply", "are", "for", "how", "in", "is", "it",
        "of", "on", "or", "the", "this", "to", "what", "with",
    }

    def __init__(
        self,
        *,
        student_id: int,
        session_factory: async_sessionmaker[AsyncSession],
        thread_subject_id: int | None = None,
    ) -> None:
        self.student_id = student_id
        self.session_factory = session_factory
        self.thread_subject_id = thread_subject_id
        self.repository = LearnerChatRepository()

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "get_my_learning_profile": self.learning_profile,
            "get_my_test_history": self.test_history,
            "search_my_completed_questions": self.completed_questions,
            "review_my_completed_question": self.completed_question_review,
            "search_subject_knowledge": self.subject_knowledge,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": "Unknown learner tool"}
        try:
            return await handler(**arguments)
        except (TypeError, ValueError) as error:
            return {"error": str(error)}

    async def learning_profile(
        self, subject_code: str | None = None
    ) -> dict[str, Any]:
        normalized = await self._allowed_subject_code(subject_code)
        profile = await LearnerProfileService(
            LearnerProfileRepository(), self.session_factory
        ).profile(self.student_id, normalized)
        return {
            "learner_profile": profile.model_dump(mode="json") if profile else None,
            "scope": normalized or "all subjects",
        }

    async def test_history(
        self, subject_code: str | None = None
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            subject_id = await self._allowed_subject_id(session, subject_code)
            rows = await self.repository.learner_history(
                session,
                student_id=self.student_id,
                subject_id=subject_id,
            )
        return {"completed_test_history": rows}

    async def completed_questions(
        self,
        query: str,
        subject_code: str | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            subject_id = await self._allowed_subject_id(session, subject_code)
            rows = await self.repository.completed_questions(
                session,
                student_id=self.student_id,
                subject_id=subject_id,
                limit=300,
            )
        return {
            "completed_questions": self._rank(rows, query, min(max(limit, 1), 5)),
            "ownership_verified": True,
            "completed_tests_only": True,
        }

    async def completed_question_review(
        self, question_code: str
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            row = await self.repository.answered_question(
                session,
                student_id=self.student_id,
                session_id=None,
                question_code=question_code,
            )
        if row is None:
            return {
                "error": "This question was not found in the learner's completed tests."
            }
        return {
            "completed_question": row,
            "ownership_verified": True,
            "review_allowed": True,
        }

    async def subject_knowledge(
        self,
        query: str,
        subject_code: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            subject_id = await self._allowed_subject_id(session, subject_code)
            rows = await self.repository.knowledge_resources(
                session,
                subject_id=subject_id,
                limit=1000,
            )
        return {
            "knowledge": self._rank(
                rows,
                query,
                min(max(limit, 1), 8),
                knowledge=True,
            ),
            "answer_options_included": False,
            "correct_answers_included": False,
        }

    async def _allowed_subject_code(self, subject_code: str | None) -> str | None:
        async with self.session_factory() as session:
            subject_id = await self._allowed_subject_id(session, subject_code)
            if subject_id is None:
                return None
            rows = await self.repository.knowledge_resources(
                session, subject_id=subject_id, limit=1
            )
        return rows[0]["subject_code"] if rows else None

    async def _allowed_subject_id(
        self,
        session: AsyncSession,
        subject_code: str | None,
    ) -> int | None:
        requested = await self.repository.subject_id(session, subject_code)
        if subject_code and requested is None:
            raise ValueError("Subject not found")
        if self.thread_subject_id is not None:
            if requested is not None and requested != self.thread_subject_id:
                raise ValueError("The conversation is scoped to another subject")
            return self.thread_subject_id
        return requested

    @classmethod
    def _rank(
        cls,
        rows: list[dict[str, Any]],
        query: str,
        limit: int,
        *,
        knowledge: bool = False,
    ) -> list[dict[str, Any]]:
        query_text = cls._normalize(query)
        tokens = cls._tokens(query)
        ranked = []
        for index, row in enumerate(rows):
            searchable = " ".join(cls._flatten(row))
            overlap = len(tokens & cls._tokens(searchable))
            score = 5 * overlap
            for key in ("question_code", "criterion_code", "resource_id"):
                code = cls._normalize(row.get(key) or "")
                if code and code in query_text:
                    score += 100
            if (
                knowledge
                and overlap
                and row.get("resource_type") == "subject_knowledge"
            ):
                score += 20
            if score:
                ranked.append((score, -index, row))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in ranked[:limit]]

    @classmethod
    def _flatten(cls, value: Any) -> list[str]:
        if isinstance(value, dict):
            return [part for item in value.values() for part in cls._flatten(item)]
        if isinstance(value, list):
            return [part for item in value for part in cls._flatten(item)]
        return [str(value or "")]

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", cls._normalize(value))
            if len(token) > 1 and token not in cls._STOP_WORDS
        }

    @staticmethod
    def _normalize(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        return " ".join(
            normalized.encode("ascii", "ignore").decode("ascii").lower().split()
        )


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }
