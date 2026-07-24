from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.auth.schemas import AuthenticatedUser
from backend.exams.errors import ExamError
from backend.kb.inference import InferenceEngine
from backend.kb.models import Clause, Fact, Rule
from backend.kb.repository import KnowledgeBaseRepository
from backend.kb.schemas import parse_relation, parse_rule
from backend.takers.repository import TakerRepository
from backend.takers.schemas import (
    LearningPathStep,
    SubjectProgress,
    TakerDashboardResponse,
    TestHistoryItem,
)


class TakerService:
    def __init__(
        self,
        repository: TakerRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory

    async def dashboard(self, user: AuthenticatedUser) -> TakerDashboardResponse:
        if user.student_id is None:
            raise ExamError("The authenticated account is not linked to a student")
        async with self._session_factory() as session:
            summary = await self._repository.summary(session, user.student_id)
            progress_rows = await self._repository.subject_progress(
                session,
                user.student_id,
            )
            history_rows = await self._repository.recent_tests(
                session,
                user.student_id,
            )
            evidence_rows = await self._repository.unit_evidence(
                session,
                user.student_id,
            )
            kb_repository = KnowledgeBaseRepository()
            rules = [parse_rule(row) for row in await kb_repository.rules(session)]
            relations = [
                parse_relation(row) for row in await kb_repository.relations(session)
            ]

        subject_progress = [
            SubjectProgress(
                **row,
                understanding_label=self._understanding_label(
                    float(row["latest_score_percent"])
                    if row["latest_score_percent"] is not None
                    else None
                ),
            )
            for row in progress_rows
        ]
        recent_tests = [
            TestHistoryItem(
                **row,
                understanding_label=self._understanding_label(
                    float(row["score_percent"])
                ),
            )
            for row in history_rows
        ]
        return TakerDashboardResponse(
            summary=summary,
            subject_progress=subject_progress,
            recent_tests=recent_tests,
            learning_path=self._build_learning_path(
                evidence_rows,
                progress_rows,
                user.student_code or str(user.student_id),
                InferenceEngine(rules, relations),
            ),
        )

    def _build_learning_path(
        self,
        evidence_rows: list[dict],
        progress_rows: list[dict],
        student_code: str = "student",
        engine: InferenceEngine | None = None,
    ) -> list[LearningPathStep]:
        if engine is None:
            engine = self._fallback_learning_engine()
        result = engine.infer(
            [
                Fact(
                    "unit_accuracy",
                    (student_code, row["unit_code"], float(row["accuracy_percent"]) / 100),
                    source="response_history",
                )
                for row in evidence_rows
            ]
        )
        recommendations = {
            str(fact.arguments[1]): str(fact.arguments[2])
            for fact in result.derived_facts
            if fact.predicate == "recommended_next" and len(fact.arguments) == 3
        }
        actions = {
            "remediate": "Ôn lại kiến thức nền và làm bài luyện tập cơ bản",
            "reinforce": "Luyện thêm bài tập để củng cố",
            "advance": "Tiếp tục với bài tập vận dụng cao hơn",
        }
        steps: list[LearningPathStep] = []
        for row in evidence_rows:
            accuracy = float(row["accuracy_percent"])
            recommendation = recommendations.get(
                row["unit_code"],
                "reinforce",
            )
            action = actions.get(recommendation, "Tiếp tục học theo lộ trình đề xuất")
            steps.append(
                LearningPathStep(
                    priority=0,
                    subject_code=row["subject_code"],
                    subject_name=row["subject_name"],
                    unit_code=row["unit_code"],
                    unit_name=row["unit_name"],
                    unit_type=row["unit_type"],
                    accuracy_percent=round(accuracy, 2),
                    evidence_count=row["evidence_count"],
                    action=action,
                    explanation=(
                        f"Dựa trên {row['evidence_count']} câu đã trả lời, mức chính xác "
                        f"ở {row['unit_name']} là {accuracy:.1f}%."
                    ),
                )
            )

        attempted_subjects = {row["subject_code"] for row in evidence_rows}
        for row in progress_rows:
            if row["subject_code"] in attempted_subjects:
                continue
            steps.append(
                LearningPathStep(
                    priority=0,
                    subject_code=row["subject_code"],
                    subject_name=row["subject_name"],
                    unit_code=None,
                    unit_name=row["subject_name"],
                    unit_type="subject",
                    accuracy_percent=None,
                    evidence_count=0,
                    action="Hoàn thành bài đánh giá đầu tiên",
                    explanation="Chưa có bằng chứng làm bài cho môn học này.",
                )
            )

        steps.sort(
            key=lambda step: (
                step.accuracy_percent is not None,
                step.accuracy_percent if step.accuracy_percent is not None else -1,
                -step.evidence_count,
                step.subject_name,
            )
        )
        selected = steps[:10]
        return [step.model_copy(update={"priority": index}) for index, step in enumerate(selected, 1)]

    @staticmethod
    def _fallback_learning_engine() -> InferenceEngine:
        def recommendation(code: str, operator: str, right: float, action: str) -> Rule:
            conditions = [
                Clause(
                    predicate="unit_accuracy",
                    arguments=("?student", "?unit", "?accuracy"),
                ),
                Clause(operator=operator, left="?accuracy", right=right),
            ]
            if action == "reinforce":
                conditions.append(Clause(operator="lt", left="?accuracy", right=0.75))
            return Rule(
                code=code,
                name=code,
                hypothesis=tuple(conditions),
                goals=(
                    Clause(
                        predicate="recommended_next",
                        arguments=("?student", "?unit", action),
                    ),
                ),
            )

        return InferenceEngine(
            (
                recommendation("R_LEARNING_REMEDIATE", "lt", 0.5, "remediate"),
                recommendation("R_LEARNING_REINFORCE", "gte", 0.5, "reinforce"),
                recommendation("R_LEARNING_ADVANCE", "gte", 0.75, "advance"),
            )
        )

    @staticmethod
    def _understanding_label(percentage: float | None) -> str:
        if percentage is None:
            return "Chưa có bài đánh giá"
        if percentage < 50:
            return "Cần ôn tập thêm"
        if percentage < 70:
            return "Đã hiểu kiến thức cơ bản"
        if percentage < 85:
            return "Hiểu tốt"
        return "Hiểu rất tốt"
