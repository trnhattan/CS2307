import math
from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.calibration.repository import CalibrationRepository
from backend.calibration.schemas import CalibrationSummary, ItemCalibration
from backend.irt.model import probability_3pl


class CalibrationService:
    def __init__(
        self,
        repository: CalibrationRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory

    async def run(self, actor: str, apply_eligible: bool) -> CalibrationSummary:
        async with self._session_factory() as session:
            config = await self._repository.config(session)
            rows = await self._repository.responses(session)
            minimum = int(config.get("IRT_CALIBRATION_MIN_RESPONSES", 30))
            apply_minimum = int(config.get("IRT_CALIBRATION_APPLY_MIN_RESPONSES", 100))
            scale = float(config.get("IRT_SCALE_CONSTANT", 1.7))
            grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                grouped[int(row["question_id"])].append(row)

            items = []
            applied_items = 0
            for question_rows in grouped.values():
                item = self._evaluate(question_rows, minimum, apply_minimum, scale)
                should_apply = bool(
                    apply_eligible
                    and item["reliability"] == "eligible"
                    and item["suggested_b"] is not None
                )
                item["applied"] = should_apply
                if should_apply:
                    await self._repository.apply_item(
                        session,
                        question_id=int(question_rows[0]["question_id"]),
                        suggested_b=float(item["suggested_b"]),
                        sample_size=int(item["sample_size"]),
                        actor=actor,
                    )
                    applied_items += 1
                items.append(item)

            eligible_items = sum(item["reliability"] == "eligible" for item in items)
            limitations = self._limitations(rows, items, minimum, apply_minimum)
            saved = await self._repository.create_run(
                session,
                actor=actor,
                minimum_sample=minimum,
                minimum_apply_sample=apply_minimum,
                total_responses=len(rows),
                evaluated_items=len(items),
                eligible_items=eligible_items,
                applied_items=applied_items,
                limitations=limitations,
                items=items,
            )
            await session.commit()
        return CalibrationSummary(
            run_id=saved["run_id"],
            method="conditional-mle-grid-v1",
            total_responses=len(rows),
            evaluated_items=len(items),
            eligible_items=eligible_items,
            applied_items=applied_items,
            minimum_evaluation_sample=minimum,
            minimum_apply_sample=apply_minimum,
            created_by=actor,
            created_at=saved["created_at"],
            limitations=limitations,
            items=[ItemCalibration(**item) for item in items],
        )

    async def latest(self) -> CalibrationSummary | None:
        async with self._session_factory() as session:
            row = await self._repository.latest(session)
        if row is None:
            return None
        summary = row["summary"]
        return CalibrationSummary(
            run_id=row["run_id"],
            method=row["method"],
            total_responses=row["total_responses"],
            evaluated_items=row["evaluated_items"],
            eligible_items=row["eligible_items"],
            applied_items=row["applied_items"],
            minimum_evaluation_sample=summary["minimum_evaluation_sample"],
            minimum_apply_sample=summary["minimum_apply_sample"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            limitations=summary["limitations"],
            items=[ItemCalibration(**item) for item in summary["items"]],
        )

    @staticmethod
    def _evaluate(
        rows: list[dict[str, Any]],
        minimum: int,
        apply_minimum: int,
        scale: float,
    ) -> dict[str, Any]:
        first = rows[0]
        answers = [1.0 if row["is_correct"] else 0.0 for row in rows]
        thetas = [float(row["theta_before"]) for row in rows]
        times = [float(row["response_time_sec"]) for row in rows if row["response_time_sec"] is not None]
        a = float(first["irt_a"])
        current_b = float(first["irt_b"])
        c = float(first["irt_c"])
        predicted = [probability_3pl(theta, a, current_b, c, scale=scale) for theta in thetas]
        sample_size = len(rows)
        has_variation = len(set(answers)) > 1 and len(set(thetas)) > 1
        suggested_b = CalibrationService._estimate_b(thetas, answers, a, c, scale) if has_variation else None
        if sample_size < minimum:
            reliability = "insufficient"
        elif sample_size < apply_minimum or not has_variation:
            reliability = "provisional"
        else:
            reliability = "eligible"
        return {
            "question_code": str(first["question_code"]),
            "subject_code": str(first["subject_code"]),
            "sample_size": sample_size,
            "observed_accuracy": round(sum(answers) / sample_size, 6),
            "predicted_accuracy": round(sum(predicted) / sample_size, 6),
            "mean_response_time_sec": round(sum(times) / len(times), 2) if times else None,
            "point_biserial": CalibrationService._correlation(thetas, answers),
            "fit_rmse": CalibrationService._binned_fit_rmse(thetas, answers, predicted),
            "current_b": current_b,
            "suggested_b": suggested_b,
            "reliability": reliability,
            "applied": False,
        }

    @staticmethod
    def _estimate_b(
        thetas: list[float],
        answers: list[float],
        a: float,
        c: float,
        scale: float,
    ) -> float:
        best_b = 0.0
        best_loss = math.inf
        for step in range(401):
            b = -4.0 + step * 0.02
            loss = 0.0
            for theta, answer in zip(thetas, answers, strict=True):
                probability = min(1 - 1e-9, max(1e-9, probability_3pl(theta, a, b, c, scale=scale)))
                loss -= answer * math.log(probability) + (1 - answer) * math.log(1 - probability)
            if loss < best_loss:
                best_loss = loss
                best_b = b
        return round(best_b, 4)

    @staticmethod
    def _correlation(left: list[float], right: list[float]) -> float | None:
        if len(left) < 2:
            return None
        mean_left = sum(left) / len(left)
        mean_right = sum(right) / len(right)
        numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right, strict=True))
        denominator = math.sqrt(
            sum((x - mean_left) ** 2 for x in left)
            * sum((y - mean_right) ** 2 for y in right)
        )
        return round(numerator / denominator, 6) if denominator else None

    @staticmethod
    def _binned_fit_rmse(
        thetas: list[float], answers: list[float], predicted: list[float]
    ) -> float | None:
        bins: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for theta, answer, probability in zip(thetas, answers, predicted, strict=True):
            key = 0 if theta < -1 else 1 if theta < 0 else 2 if theta < 1 else 3
            bins[key].append((answer, probability))
        squared = []
        for values in bins.values():
            if len(values) < 2:
                continue
            observed = sum(value[0] for value in values) / len(values)
            expected = sum(value[1] for value in values) / len(values)
            squared.append((observed - expected) ** 2)
        return round(math.sqrt(sum(squared) / len(squared)), 6) if squared else None

    @staticmethod
    def _limitations(
        rows: list[dict[str, Any]],
        items: list[dict[str, Any]],
        minimum: int,
        apply_minimum: int,
    ) -> list[str]:
        limitations = []
        if not rows:
            limitations.append("No real completed responses are available for empirical calibration.")
            return limitations
        insufficient = sum(item["sample_size"] < minimum for item in items)
        if insufficient:
            limitations.append(
                f"{insufficient} items have fewer than {minimum} real responses and are descriptive only."
            )
        if not any(item["sample_size"] >= apply_minimum for item in items):
            limitations.append(
                f"No item has the {apply_minimum} responses required to update production IRT parameters."
            )
        limitations.append(
            "The conditional estimator holds discrimination and guessing fixed; a larger diverse sample is required for full 3PL calibration."
        )
        return limitations
