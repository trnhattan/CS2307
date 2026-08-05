from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.learner_profiles.repository import LearnerProfileRepository
from backend.learner_profiles.schemas import (
    CriteriaCatalogResponse,
    CriterionDefinition,
    CriterionRadarResponse,
    CriterionState,
    LearnerProfileResponse,
    ProfileRecommendation,
    RadarAxis,
    SubjectLearnerProfile,
)


class LearnerProfileService:
    def __init__(
        self,
        repository: LearnerProfileRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.repository = repository
        self.session_factory = session_factory

    async def catalog(self, subject_code: str) -> CriteriaCatalogResponse | None:
        async with self.session_factory() as session:
            rows = await self.repository.criteria(session, subject_code.upper())
        if not rows:
            return None
        return CriteriaCatalogResponse(
            subject_code=rows[0]["subject_code"],
            subject_name=rows[0]["subject_name"],
            criteria=[CriterionDefinition(**self._normalized(row)) for row in rows],
        )

    async def profile(
        self, student_id: int, subject_code: str | None = None
    ) -> LearnerProfileResponse | None:
        normalized_code = subject_code.upper() if subject_code else None
        async with self.session_factory() as session:
            student = await self.repository.student(session, student_id)
            if student is None:
                return None
            rows = await self.repository.states(session, student_id, normalized_code)
            config = await self.repository.config(session)
        threshold = float(config.get("PROFILE_IMPROVEMENT_DELTA", 0.05))
        subjects: dict[str, list[CriterionState]] = defaultdict(list)
        for row in rows:
            state = self._state(row, threshold)
            subjects[state.subject_code].append(state)
        return LearnerProfileResponse(
            student_id=student_id,
            student_code=student["student_code"],
            student_name=student["display_name"],
            subjects=[self._subject_profile(values) for values in subjects.values()],
        )

    async def radar(
        self, student_id: int, subject_code: str
    ) -> CriterionRadarResponse | None:
        if subject_code.upper() == "OVERALL":
            return await self.overall_radar(student_id)
        profile = await self.profile(student_id, subject_code)
        if profile is None or not profile.subjects:
            return None
        subject = profile.subjects[0]
        axes = [
            RadarAxis(
                criterion_code=item.criterion_code,
                criterion_name=item.criterion_name,
                value_percent=(
                    round(item.mastery_probability * 100, 2)
                    if item.mastery_probability is not None and item.evidence_count > 0
                    else None
                ),
                evidence_count=item.evidence_count,
                evidence_confidence=item.evidence_confidence,
                understanding_label=item.understanding_label,
            )
            for item in subject.criteria
        ]
        assessed = sum(axis.value_percent is not None for axis in axes)
        return CriterionRadarResponse(
            subject_code=subject.subject_code,
            subject_name=subject.subject_name,
            scope="subject",
            axes=axes,
            assessed_criteria=assessed,
            total_criteria=len(axes),
            note=(
                "Unassessed criteria are reported as unknown and are not converted to zero."
            ),
        )

    async def overall_radar(
        self, student_id: int
    ) -> CriterionRadarResponse | None:
        async with self.session_factory() as session:
            student = await self.repository.student(session, student_id)
            if student is None:
                return None
            rows = await self.repository.subject_states(session, student_id)
        axes = []
        for row in rows:
            completed_tests = int(row["completed_tests"] or 0)
            evidence_count = int(row["evidence_count"] or 0)
            mastery = (
                float(row["mastery_probability"])
                if row["mastery_probability"] is not None and completed_tests > 0
                else None
            )
            axes.append(
                RadarAxis(
                    criterion_code=row["subject_code"],
                    criterion_name=row["subject_name"],
                    value_percent=(round(mastery * 100, 2) if mastery is not None else None),
                    evidence_count=evidence_count,
                    evidence_confidence=self._confidence(completed_tests),
                    understanding_label=self._understanding(mastery, evidence_count),
                )
            )
        assessed = sum(axis.value_percent is not None for axis in axes)
        return CriterionRadarResponse(
            subject_code="OVERALL",
            subject_name="Overall subject mastery",
            scope="overall",
            axes=axes,
            assessed_criteria=assessed,
            total_criteria=len(axes),
            note=(
                "Each axis is the current IRT-derived subject mastery. Subjects without "
                "a completed assessment remain unknown rather than zero."
            ),
        )

    @classmethod
    def _state(cls, row: dict[str, Any], delta_threshold: float) -> CriterionState:
        normalized = cls._normalized(row)
        evidence = int(row["evidence_count"] or 0)
        mastery = (
            float(row["mastery_probability"])
            if row["mastery_probability"] is not None and evidence > 0
            else None
        )
        delta = (
            float(row["mastery_delta"])
            if row["mastery_delta"] is not None
            else None
        )
        return CriterionState(
            **normalized,
            mastery_probability=mastery,
            accuracy_percent=(
                round(float(row["accuracy_percent"]), 2)
                if row["accuracy_percent"] is not None
                else None
            ),
            evidence_count=evidence,
            understanding_label=cls._understanding(mastery, evidence),
            evidence_confidence=cls._confidence(evidence),
            trend=cls._trend(delta, delta_threshold, evidence),
            mastery_delta=round(delta, 4) if delta is not None else None,
            last_assessed_at=row["last_assessed_at"],
        )

    @staticmethod
    def _normalized(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "criterion_id": int(row["criterion_id"]),
            "criterion_code": row["criterion_code"],
            "criterion_name": row["criterion_name"],
            "subject_code": row["subject_code"],
            "subject_name": row["subject_name"],
            "topic_code": row.get("topic_code"),
            "topic_name": row.get("topic_name"),
            "learning_objective": row["learning_objective"],
            "success_statement": row["success_statement"],
            "mastery_threshold": float(row["mastery_threshold"]),
            "importance_weight": float(row["importance_weight"]),
            "display_order": int(row["display_order"]),
            "mapped_question_count": int(row["mapped_question_count"] or 0),
        }

    @classmethod
    def _subject_profile(cls, criteria: list[CriterionState]) -> SubjectLearnerProfile:
        first = criteria[0]
        strengths = [
            item.criterion_name
            for item in criteria
            if item.mastery_probability is not None
            and item.mastery_probability >= item.mastery_threshold
        ]
        weaknesses = [
            item.criterion_name
            for item in criteria
            if item.mastery_probability is not None and item.mastery_probability < 0.5
        ]
        improved = [item.criterion_name for item in criteria if item.trend == "improved"]
        regressed = [item.criterion_name for item in criteria if item.trend == "regressed"]
        unknown = [
            item.criterion_name for item in criteria if item.evidence_count == 0
        ]
        ranked = sorted(
            criteria,
            key=lambda item: (
                item.evidence_count > 0,
                item.mastery_probability if item.mastery_probability is not None else -1,
                -item.importance_weight,
                item.display_order,
            ),
        )
        recommendations = []
        for priority, item in enumerate(ranked[:5], 1):
            if item.evidence_count == 0:
                action = "Complete diagnostic questions for this criterion"
                reason = "No scored evidence is available yet."
            elif item.mastery_probability is not None and item.mastery_probability < 0.5:
                action = "Review the foundation, then complete guided practice"
                reason = (
                    f"Current understanding is {item.understanding_label.lower()} from "
                    f"{item.evidence_count} answered questions."
                )
            else:
                action = "Complete targeted reinforcement practice"
                reason = (
                    f"More evidence is needed to confirm mastery of {item.criterion_name}."
                )
            recommendations.append(
                ProfileRecommendation(
                    criterion_code=item.criterion_code,
                    criterion_name=item.criterion_name,
                    action=action,
                    reason=reason,
                    priority=priority,
                )
            )
        return SubjectLearnerProfile(
            subject_code=first.subject_code,
            subject_name=first.subject_name,
            criteria=criteria,
            strengths=strengths,
            weaknesses=weaknesses,
            improved=improved,
            regressed=regressed,
            insufficient_evidence=unknown,
            recommendations=recommendations,
        )

    @staticmethod
    def _understanding(mastery: float | None, evidence: int) -> str:
        if mastery is None or evidence == 0:
            return "Not assessed"
        if mastery < 0.5:
            return "Needs review"
        if mastery < 0.75:
            return "Developing"
        return "Mastered"

    @staticmethod
    def _confidence(evidence: int) -> str:
        if evidence == 0:
            return "No evidence"
        if evidence < 3:
            return "Low"
        if evidence < 5:
            return "Moderate"
        return "Strong"

    @staticmethod
    def _trend(delta: float | None, threshold: float, evidence: int) -> str:
        if evidence == 0:
            return "not_assessed"
        if delta is None:
            return "baseline"
        if delta >= threshold:
            return "improved"
        if delta <= -threshold:
            return "regressed"
        return "stable"
