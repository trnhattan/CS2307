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
            evidence_rows = await self._repository.criterion_mastery(
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
                    "criterion_mastery",
                    (student_code, row["unit_code"], float(row["mastery_probability"])),
                    source="response_history",
                )
                for row in evidence_rows
                if row.get("mastery_probability") is not None
                and int(row.get("evidence_count") or 0) > 0
            ]
        )
        recommendations = {
            str(fact.arguments[1]): str(fact.arguments[2])
            for fact in result.derived_facts
            if fact.predicate == "recommended_next" and len(fact.arguments) == 3
        }
        actions = {
            "remediate": "Review prerequisite knowledge and complete foundational practice",
            "develop": "Build understanding with guided examples and focused practice",
            "reinforce": "Complete targeted practice to consolidate understanding",
        }
        steps: list[LearningPathStep] = []
        for row in evidence_rows:
            mastery = (
                float(row["mastery_probability"])
                if row.get("mastery_probability") is not None
                and int(row.get("evidence_count") or 0) > 0
                else None
            )
            mastery_threshold = float(row.get("mastery_threshold") or 0.75)
            if mastery is None or mastery >= mastery_threshold:
                continue
            recommendation = recommendations.get(
                row["unit_code"],
                self._recommendation_for_mastery(mastery),
            )
            action = actions.get(recommendation, "Continue with the recommended learning path")
            mastery_percent = round(mastery * 100, 2)
            steps.append(
                LearningPathStep(
                    priority=0,
                    subject_code=row["subject_code"],
                    subject_name=row["subject_name"],
                    unit_code=row["unit_code"],
                    unit_name=row["unit_name"],
                    unit_type=row["unit_type"],
                    accuracy_percent=mastery_percent,
                    mastery_percent=mastery_percent,
                    understanding_label=self._criterion_understanding(mastery),
                    evidence_count=row["evidence_count"],
                    action=action,
                    explanation=(
                        f"Current criterion mastery is {mastery_percent:.1f}% from "
                        f"{row['evidence_count']} answered questions."
                    ),
                )
            )

        attempted_subjects = {
            row["subject_code"]
            for row in evidence_rows
            if row.get("mastery_probability") is not None
            and int(row.get("evidence_count") or 0) > 0
        }
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
                    mastery_percent=None,
                    understanding_label="Not assessed",
                    evidence_count=0,
                    action="Complete the first assessment",
                    explanation="No completed-response evidence exists for this subject.",
                )
            )

        grouped: dict[str, list[LearningPathStep]] = {}
        for step in steps:
            grouped.setdefault(step.subject_code, []).append(step)
        ordered: list[LearningPathStep] = []
        for subject_code in sorted(
            grouped,
            key=lambda code: (grouped[code][0].subject_name, code),
        ):
            subject_steps = sorted(
                grouped[subject_code],
                key=lambda step: (
                    step.mastery_percent is not None,
                    step.mastery_percent if step.mastery_percent is not None else -1,
                    -step.evidence_count,
                    step.unit_name,
                ),
            )
            ordered.extend(
                step.model_copy(update={"priority": index})
                for index, step in enumerate(subject_steps, 1)
            )
        return ordered

    @staticmethod
    def _fallback_learning_engine() -> InferenceEngine:
        def recommendation(
            code: str,
            operator: str,
            right: float,
            action: str,
            upper: float | None = None,
        ) -> Rule:
            conditions = [
                Clause(
                    predicate="criterion_mastery",
                    arguments=("?student", "?unit", "?mastery"),
                ),
                Clause(operator=operator, left="?mastery", right=right),
            ]
            if upper is not None:
                conditions.append(Clause(operator="lt", left="?mastery", right=upper))
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
                recommendation("R_CRITERION_REMEDIATE", "lt", 0.45, "remediate"),
                recommendation("R_CRITERION_DEVELOP", "gte", 0.45, "develop", 0.60),
                recommendation("R_CRITERION_REINFORCE", "gte", 0.60, "reinforce", 0.75),
            )
        )

    @staticmethod
    def _recommendation_for_mastery(mastery: float) -> str:
        if mastery < 0.45:
            return "remediate"
        if mastery < 0.60:
            return "develop"
        return "reinforce"

    @staticmethod
    def _criterion_understanding(mastery: float) -> str:
        if mastery < 0.45:
            return "Needs review"
        if mastery < 0.60:
            return "Developing"
        if mastery < 0.75:
            return "Understands"
        return "Mastered"

    @staticmethod
    def _understanding_label(percentage: float | None) -> str:
        if percentage is None:
            return "Not assessed"
        if percentage < 50:
            return "Needs review"
        if percentage < 70:
            return "Foundational understanding"
        if percentage < 85:
            return "Good understanding"
        return "Strong understanding"
