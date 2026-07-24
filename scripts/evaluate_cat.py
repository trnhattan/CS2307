import asyncio
import csv
import json
from collections import defaultdict
from io import StringIO
from pathlib import Path

from sqlalchemy import text

from backend.db.session import async_session_factory, engine
from backend.evaluation.simulator import EvaluationItem, evaluate_cat


ROOT = Path(__file__).resolve().parents[1]


async def load_inputs() -> tuple[dict[str, list[EvaluationItem]], dict, dict[str, str]]:
    async with async_session_factory() as session:
        config_result = await session.execute(
            text("SELECT prop_key, prop_value FROM sys_props")
        )
        config = {row.prop_key: row.prop_value for row in config_result}
        result = await session.execute(
            text(
                """
                WITH active_counts AS (
                    SELECT subject_id, COUNT(*) AS active_count
                    FROM questions
                    WHERE status = 'active'
                    GROUP BY subject_id
                )
                SELECT subject.subject_code, question.question_id,
                       question.question_code, question.difficulty_label,
                       question.difficulty_norm, question.bloom_level,
                       question.avg_time_sec, question.irt_a,
                       question.irt_b, question.irt_c,
                       COALESCE(MAX(unit.unit_code) FILTER (
                           WHERE link.unit_role = 'topic'
                       ), 'GENERAL') AS topic_code,
                       COALESCE(ARRAY_AGG(DISTINCT unit.unit_code) FILTER (
                           WHERE unit.unit_code IS NOT NULL
                       ), ARRAY[]::VARCHAR[]) AS unit_codes,
                       CASE WHEN COALESCE(active.active_count, 0) > 0
                            THEN 'active'
                            ELSE 'validated_existing_offline'
                       END AS pool_mode
                FROM questions question
                JOIN subjects subject ON subject.subject_id = question.subject_id
                JOIN v_question_pool_validation validation
                  ON validation.question_id = question.question_id
                 AND validation.is_pool_valid = TRUE
                LEFT JOIN active_counts active ON active.subject_id = question.subject_id
                LEFT JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                LEFT JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                WHERE (COALESCE(active.active_count, 0) = 0 OR question.status = 'active')
                  AND question.explanation IS NOT NULL
                  AND trim(question.explanation) <> ''
                  AND question.source IS NOT NULL
                  AND trim(question.source) <> ''
                  AND question.provenance <> '{}'::JSONB
                GROUP BY subject.subject_id, question.question_id, active.active_count
                HAVING COUNT(DISTINCT link.unit_id) FILTER (
                           WHERE link.unit_role = 'topic'
                       ) = 1
                   AND COUNT(DISTINCT link.unit_id) FILTER (
                           WHERE link.unit_role = 'primary_skill'
                       ) = 1
                ORDER BY subject.subject_code, question.question_code
                """
            )
        )
        groups: dict[str, list[EvaluationItem]] = defaultdict(list)
        modes: dict[str, str] = {}
        for row in result:
            groups[row.subject_code].append(
                EvaluationItem(
                    question_id=row.question_id,
                    question_code=row.question_code,
                    difficulty_label=row.difficulty_label,
                    difficulty_norm=float(row.difficulty_norm),
                    bloom_level=row.bloom_level,
                    topic_code=row.topic_code,
                    unit_codes=tuple(row.unit_codes),
                    irt_a=float(row.irt_a),
                    irt_b=float(row.irt_b),
                    irt_c=float(row.irt_c),
                    avg_time_sec=row.avg_time_sec,
                )
            )
            modes[row.subject_code] = row.pool_mode
    return dict(groups), config, modes


def evaluate_subjects(
    groups: dict[str, list[EvaluationItem]], config: dict, modes: dict[str, str]
) -> dict:
    if not groups:
        raise ValueError("No valid existing questions are available for CAT evaluation")
    parameters = {
        "minimum": int(config.get("CAT_MIN_QUESTION_COUNT", 10)),
        "maximum": int(config.get("CAT_MAX_QUESTION_COUNT", 30)),
        "se_threshold": float(config.get("CAT_STOP_STANDARD_ERROR", 0.3)),
        "epsilon": float(config.get("CAT_STABILITY_EPSILON", 0.05)),
        "stability_window": int(config.get("CAT_STABILITY_WINDOW", 3)),
        "scale": float(config.get("IRT_SCALE_CONSTANT", 1.7)),
        "difficulty_distribution": config.get(
            "CAT_DIFFICULTY_DISTRIBUTION",
            {"easy": 0.3, "medium": 0.4, "hard": 0.3},
        ),
        "information_weight": float(config.get("CAT_INFORMATION_WEIGHT", 1.0)),
        "weak_unit_weight": float(config.get("CAT_WEAK_UNIT_WEIGHT", 0.35)),
        "content_balance_weight": float(
            config.get("CAT_CONTENT_BALANCE_WEIGHT", 0.2)
        ),
        "exposure_penalty": float(config.get("CAT_EXPOSURE_PENALTY", 0.15)),
    }
    subjects = {}
    for subject_code, items in sorted(groups.items()):
        result = evaluate_cat(items, **parameters).as_dict()
        result["pool_mode"] = modes[subject_code]
        if modes[subject_code] != "active":
            result["limitations"].insert(
                0,
                "No active items exist for this subject; the offline evaluation uses only "
                "existing records that pass deterministic structural checks. They remain "
                "ineligible for production CAT until explicit admin review and activation.",
            )
        subjects[subject_code] = result
    return {
        "source": "existing_postgresql_question_bank",
        "generated_questions": 0,
        "config": parameters,
        "subjects": subjects,
        "question_count": sum(len(items) for items in groups.values()),
    }


def write_outputs(payload: dict) -> None:
    output_dir = ROOT / "data" / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cat_metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["subject", "step", "mean_standard_error"])
    for subject_code, result in payload["subjects"].items():
        for step, value in result["mean_se_by_step"].items():
            writer.writerow([subject_code, step, value])
    (output_dir / "cat_se_by_step.csv").write_text(
        stream.getvalue(), encoding="utf-8"
    )
    rows = []
    limitations = []
    for subject_code, result in payload["subjects"].items():
        rows.append(
            f"| {subject_code} | {result['pool_mode']} | {result['question_count']} | "
            f"{result['rmse']:.4f} | {result['mae']:.4f} | {result['bias']:.4f} | "
            f"{result['mean_questions']:.2f} | {result['convergence_rate']:.2%} |"
        )
        limitations.extend(
            f"- **{subject_code}:** {value}" for value in result["limitations"]
        )
    report = f"""# CAT/IRT Evaluation

This deterministic report uses {payload['question_count']} existing PostgreSQL questions, grouped by subject. It generated no question content.

| Subject | Pool mode | Questions | RMSE | MAE | Bias | Mean questions | Convergence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Reliability and limitations

{chr(10).join(limitations)}
"""
    (ROOT / "docs" / "evaluation_report.md").write_text(
        report, encoding="utf-8"
    )


async def main() -> None:
    try:
        groups, config, modes = await load_inputs()
        payload = evaluate_subjects(groups, config, modes)
        write_outputs(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
