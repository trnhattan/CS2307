import argparse
import asyncio
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.abilities.service import AbilityService
from backend.auth.passwords import hash_password
from backend.db.session import async_session_factory
from backend.exams.options import prepare_display_options
from backend.irt.model import IRTResponse, estimate_ability_eap, fisher_information_3pl


PROFILE_VERSION = "alex-nguyen-growth-v2"
USERNAME = "demo_taker"
PASSWORD = "demo_taker"
STUDENT_CODE = "DEMO001"
DISPLAY_NAME = "Alex Nguyen"


@dataclass(frozen=True, slots=True)
class DemoStage:
    subject_code: str
    started_at: datetime
    score_percent: int
    purpose: str
    mode: str


STAGES = (
    DemoStage("DATABASE", datetime(2026, 1, 18, 9, 0, tzinfo=UTC), 65, "placement", "fixed"),
    DemoStage("NETWORK", datetime(2026, 2, 8, 9, 30, tzinfo=UTC), 45, "placement", "fixed"),
    DemoStage("DATABASE", datetime(2026, 3, 16, 14, 0, tzinfo=UTC), 75, "progress", "adaptive"),
    DemoStage("DATABASE", datetime(2026, 4, 19, 14, 30, tzinfo=UTC), 85, "progress", "adaptive"),
    DemoStage("NETWORK", datetime(2026, 5, 10, 10, 0, tzinfo=UTC), 55, "progress", "adaptive"),
    DemoStage("DATABASE", datetime(2026, 6, 14, 15, 0, tzinfo=UTC), 90, "progress", "adaptive"),
    DemoStage("NETWORK", datetime(2026, 7, 5, 9, 0, tzinfo=UTC), 65, "progress", "adaptive"),
    DemoStage("DATABASE", datetime(2026, 7, 26, 15, 0, tzinfo=UTC), 95, "progress", "adaptive"),
)


async def seed_demo_learner(*, replace: bool = False) -> dict[str, Any]:
    async with async_session_factory() as session:
        student_id = await _ensure_account(session)
        existing, current = await _existing_stage_counts(session, student_id)
        if existing == current == len(STAGES):
            await session.commit()
            return await _summary(session, student_id, created=False)
        if existing and not replace:
            raise RuntimeError(
                "A different or incomplete demo profile exists. Run with --replace "
                "to replace only deterministic demo-learner evidence."
            )
        if existing:
            await _remove_demo_evidence(session, student_id)

        subjects = await _subjects(session)
        question_sets = await _question_sets(session, subjects)
        response_history: dict[str, list[IRTResponse]] = defaultdict(list)
        mastered_order = {
            code: _mastered_order(code, len(question_sets[code][0]))
            for code in question_sets
        }
        stage_index_by_subject: dict[str, int] = defaultdict(int)

        for stage in STAGES:
            subject_stage = stage_index_by_subject[stage.subject_code]
            stage_index_by_subject[stage.subject_code] += 1
            questions = question_sets[stage.subject_code][subject_stage]
            correct_count = round(len(questions) * stage.score_percent / 100)
            correct_criteria = set(mastered_order[stage.subject_code][:correct_count])
            await _create_session(
                session,
                student_id=student_id,
                subject=subjects[stage.subject_code],
                stage=stage,
                questions=questions,
                correct_criteria=correct_criteria,
                response_history=response_history[stage.subject_code],
            )

        await session.commit()
        return await _summary(session, student_id, created=True)


async def _ensure_account(session: AsyncSession) -> int:
    result = await session.execute(
        text(
            """
            INSERT INTO students (student_code, display_name, is_active)
            VALUES (:student_code, :display_name, TRUE)
            ON CONFLICT (student_code) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                is_active = TRUE
            RETURNING student_id
            """
        ),
        {"student_code": STUDENT_CODE, "display_name": DISPLAY_NAME},
    )
    student_id = int(result.scalar_one())
    await session.execute(
        text(
            """
            INSERT INTO app_users (
                username, password_hash, display_name, role, student_id, is_active
            ) VALUES (
                :username, :password_hash, :display_name,
                'exam_taker', :student_id, TRUE
            )
            ON CONFLICT (username) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                display_name = EXCLUDED.display_name,
                role = 'exam_taker',
                student_id = EXCLUDED.student_id,
                is_active = TRUE
            """
        ),
        {
            "username": USERNAME,
            "password_hash": hash_password(PASSWORD, salt="cs2307-demo-taker-salt"),
            "display_name": DISPLAY_NAME,
            "student_id": student_id,
        },
    )
    return student_id


async def _existing_stage_counts(
    session: AsyncSession, student_id: int
) -> tuple[int, int]:
    result = await session.execute(
        text(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (
                       WHERE generation_config ->> 'demo_profile_version' = :profile_version
                   ) AS current
            FROM exam_sessions
            WHERE student_id = :student_id
              AND generation_config ->> 'source' = 'deterministic_demo_learner_seed'
            """
        ),
        {"student_id": student_id, "profile_version": PROFILE_VERSION},
    )
    row = result.one()
    return int(row.total), int(row.current)


async def _remove_demo_evidence(session: AsyncSession, student_id: int) -> None:
    session_rows = await session.execute(
        text(
            """
            SELECT session_id
            FROM exam_sessions
            WHERE student_id = :student_id
              AND generation_config ->> 'source' = 'deterministic_demo_learner_seed'
            """
        ),
        {"student_id": student_id},
    )
    session_ids = list(session_rows.scalars())
    if not session_ids:
        return
    trace_rows = await session.execute(
        text(
            """
            SELECT inference_trace_id
            FROM inference_traces
            WHERE session_id = ANY(CAST(:session_ids AS BIGINT[]))
            """
        ),
        {"session_ids": session_ids},
    )
    trace_ids = list(trace_rows.scalars())
    await session.execute(
        text(
            """
            DELETE FROM kb_facts
            WHERE fact_args ->> 0 = :student_code
               OR inference_trace_id = ANY(CAST(:trace_ids AS BIGINT[]))
            """
        ),
        {"student_code": STUDENT_CODE, "trace_ids": trace_ids},
    )
    await session.execute(
        text(
            """
            DELETE FROM inference_traces
            WHERE inference_trace_id = ANY(CAST(:trace_ids AS BIGINT[]))
            """
        ),
        {"trace_ids": trace_ids},
    )
    await session.execute(
        text("DELETE FROM student_abilities WHERE student_id = :student_id"),
        {"student_id": student_id},
    )
    await session.execute(
        text(
            """
            DELETE FROM exam_sessions
            WHERE session_id = ANY(CAST(:session_ids AS BIGINT[]))
            """
        ),
        {"session_ids": session_ids},
    )


async def _subjects(session: AsyncSession) -> dict[str, dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT subject_id, subject_code, subject_name
            FROM subjects
            WHERE subject_code IN ('DATABASE', 'NETWORK') AND is_active = TRUE
            """
        )
    )
    subjects = {row.subject_code: dict(row._mapping) for row in result}
    if set(subjects) != {"DATABASE", "NETWORK"}:
        raise RuntimeError("The Database Systems and Computer Networks subjects are required")
    return subjects


async def _question_sets(
    session: AsyncSession,
    subjects: dict[str, dict[str, Any]],
) -> dict[str, list[list[dict[str, Any]]]]:
    required = defaultdict(int)
    for stage in STAGES:
        required[stage.subject_code] += 1
    result = {}
    for subject_code, stage_count in required.items():
        candidates = await _criterion_questions(
            session, int(subjects[subject_code]["subject_id"])
        )
        criteria = sorted(candidates)
        if len(criteria) != 20:
            raise RuntimeError(
                f"{subject_code} requires 20 active criteria; found {len(criteria)}"
            )
        used_questions: set[int] = set()
        stages = []
        for _ in range(stage_count):
            selected = []
            for criterion_code in criteria:
                question = next(
                    (
                        item for item in candidates[criterion_code]
                        if int(item["question_id"]) not in used_questions
                    ),
                    None,
                )
                if question is None:
                    raise RuntimeError(
                        f"{subject_code}/{criterion_code} lacks distinct demo questions"
                    )
                used_questions.add(int(question["question_id"]))
                selected.append(question)
            stages.append(selected)
        result[subject_code] = stages
    return result


async def _criterion_questions(
    session: AsyncSession, subject_id: int
) -> dict[str, list[dict[str, Any]]]:
    result = await session.execute(
        text(
            """
            SELECT criterion.criterion_code, criterion.display_order,
                   question.question_id, question.question_code, question.version_no,
                   question.stem, question.display_option_count,
                   question.avg_time_sec, question.irt_a, question.irt_b,
                   question.irt_c, question.difficulty_label
            FROM assessment_criteria criterion
            JOIN question_knowledge_units link
              ON link.unit_id = criterion.knowledge_unit_id
             AND link.unit_role IN ('primary_skill', 'supporting_skill')
            JOIN questions question ON question.question_id = link.question_id
            JOIN v_question_pool_validation validation
              ON validation.question_id = question.question_id
             AND validation.is_pool_valid = TRUE
            WHERE criterion.subject_id = :subject_id
              AND criterion.is_active = TRUE
              AND question.status = 'active'
            ORDER BY criterion.display_order, criterion.criterion_code,
                     question.question_code
            """
        ),
        {"subject_id": subject_id},
    )
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result:
        candidates[row.criterion_code].append(dict(row._mapping))
    return candidates


def _mastered_order(subject_code: str, criterion_count: int) -> list[str]:
    codes = [f"criterion-{index:02d}" for index in range(criterion_count)]
    random.Random(f"{PROFILE_VERSION}:{subject_code}").shuffle(codes)
    return codes


async def _create_session(
    session: AsyncSession,
    *,
    student_id: int,
    subject: dict[str, Any],
    stage: DemoStage,
    questions: list[dict[str, Any]],
    correct_criteria: set[str],
    response_history: list[IRTResponse],
) -> None:
    initial = estimate_ability_eap(response_history)
    generation_config = {
        "demo_profile_version": PROFILE_VERSION,
        "profile": "high_database_fair_network_with_growth",
        "criterion_coverage": "one_question_per_active_criterion",
        "target_score_percent": stage.score_percent,
        "source": "deterministic_demo_learner_seed",
    }
    result = await session.execute(
        text(
            """
            INSERT INTO exam_sessions (
                student_id, subject_id, mode, assessment_purpose, status,
                generation_config, random_seed, theta_initial, theta_current,
                standard_error_current, total_score, max_score, started_at
            ) VALUES (
                :student_id, :subject_id, :mode, :purpose, 'in_progress',
                CAST(:config AS JSONB), :seed, :theta, :theta, :standard_error,
                0, :max_score, :started_at
            ) RETURNING session_id
            """
        ),
        {
            "student_id": student_id,
            "subject_id": subject["subject_id"],
            "mode": stage.mode,
            "purpose": stage.purpose,
            "config": _json(generation_config),
            "seed": int(stage.started_at.timestamp()),
            "theta": initial.theta,
            "standard_error": initial.standard_error,
            "max_score": len(questions),
            "started_at": stage.started_at,
        },
    )
    session_id = int(result.scalar_one())
    criterion_order = [f"criterion-{index:02d}" for index in range(len(questions))]
    total_score = 0
    latest = initial
    finished_at = stage.started_at

    for order_no, (question, criterion_token) in enumerate(
        zip(questions, criterion_order), 1
    ):
        options = await _options(session, int(question["question_id"]))
        displayed = prepare_display_options(
            options,
            int(question["display_option_count"]),
            seed=session_id * 10_000 + order_no,
            randomize=True,
        )
        is_correct = criterion_token in correct_criteria
        selected = next(
            item for item in displayed
            if bool(item["is_best_answer"]) is is_correct
        )
        theta_before = latest.theta
        information = fisher_information_3pl(
            theta_before,
            float(question["irt_a"]),
            float(question["irt_b"]),
            float(question["irt_c"]),
        )
        response_history.append(
            IRTResponse(
                a=float(question["irt_a"]),
                b=float(question["irt_b"]),
                c=float(question["irt_c"]),
                correct=is_correct,
            )
        )
        latest = estimate_ability_eap(response_history)
        response_seconds = _response_seconds(question, is_correct, order_no)
        presented_at = stage.started_at + timedelta(minutes=2 * (order_no - 1))
        answered_at = presented_at + timedelta(seconds=response_seconds)
        finished_at = max(finished_at, answered_at)
        total_score += int(is_correct)
        await session.execute(
            text(
                """
                INSERT INTO exam_items (
                    session_id, question_id, question_version, order_no,
                    stem_snapshot, displayed_options, selection_rule_code,
                    selection_reason, item_information, theta_before, presented_at,
                    selected_option_code, is_correct, awarded_score, irt_response,
                    response_time_sec, theta_after, standard_error_after,
                    scoring_detail, answered_at
                ) VALUES (
                    :session_id, :question_id, :version_no, :order_no,
                    :stem, CAST(:options AS JSONB), 'R_DEMO_CRITERION_COVERAGE',
                    :reason, :information, :theta_before, :presented_at,
                    :option_code, :is_correct, :score, :irt_response,
                    :response_time, :theta_after, :standard_error,
                    CAST(:scoring AS JSONB), :answered_at
                )
                """
            ),
            {
                "session_id": session_id,
                "question_id": question["question_id"],
                "version_no": question["version_no"],
                "order_no": order_no,
                "stem": question["stem"],
                "options": _json(displayed),
                "reason": (
                    "Selected to measure a distinct assessment criterion in the "
                    "deterministic demonstration profile."
                ),
                "information": information,
                "theta_before": theta_before,
                "presented_at": presented_at,
                "option_code": selected["option_code"],
                "is_correct": is_correct,
                "score": int(is_correct),
                "irt_response": int(is_correct),
                "response_time": response_seconds,
                "theta_after": latest.theta,
                "standard_error": latest.standard_error,
                "scoring": _json(
                    {
                        "source": "deterministic_demo_learner_seed",
                        "profile_version": PROFILE_VERSION,
                    }
                ),
                "answered_at": answered_at,
            },
        )

    finished_at += timedelta(minutes=1)
    await session.execute(
        text(
            """
            UPDATE exam_sessions
            SET status = 'completed', total_score = :total_score,
                theta_current = :theta, standard_error_current = :standard_error,
                finished_at = :finished_at
            WHERE session_id = :session_id
            """
        ),
        {
            "session_id": session_id,
            "total_score": total_score,
            "theta": latest.theta,
            "standard_error": latest.standard_error,
            "finished_at": finished_at,
        },
    )
    await AbilityService().refresh(
        session,
        student_id=student_id,
        subject_id=int(subject["subject_id"]),
        session_id=session_id,
    )
    await session.execute(
        text(
            """
            UPDATE student_ability_snapshots
            SET created_at = :created_at
            WHERE session_id = :session_id
            """
        ),
        {"session_id": session_id, "created_at": finished_at},
    )


async def _options(
    session: AsyncSession, question_id: int
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT option_code, option_text, score_weight, is_best_answer,
                   distractor_type, explanation, diagnosis
            FROM answer_options
            WHERE question_id = :question_id AND is_active = TRUE
            ORDER BY option_code
            """
        ),
        {"question_id": question_id},
    )
    return [dict(row._mapping) for row in result]


def _response_seconds(
    question: dict[str, Any], is_correct: bool, order_no: int
) -> int:
    multiplier = 0.82 if is_correct else 1.12
    jitter = ((order_no * 13) % 17) - 8
    return max(20, round(float(question["avg_time_sec"]) * multiplier + jitter))


async def _summary(
    session: AsyncSession, student_id: int, *, created: bool
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            SELECT subject.subject_code, COUNT(*) AS sessions,
                   ROUND(100 * AVG(exam.total_score / NULLIF(exam.max_score, 0)), 1)
                       AS average_score,
                   ROUND(100 * (
                       ARRAY_AGG(exam.total_score / NULLIF(exam.max_score, 0)
                                 ORDER BY exam.finished_at DESC)
                   )[1], 1) AS latest_score
            FROM exam_sessions exam
            JOIN subjects subject ON subject.subject_id = exam.subject_id
            WHERE exam.student_id = :student_id
              AND exam.generation_config ->> 'demo_profile_version' = :profile_version
            GROUP BY subject.subject_code
            ORDER BY subject.subject_code
            """
        ),
        {"student_id": student_id, "profile_version": PROFILE_VERSION},
    )
    return {
        "created": created,
        "username": USERNAME,
        "password": PASSWORD,
        "display_name": DISPLAY_NAME,
        "subjects": [dict(row._mapping) for row in result],
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-credentials", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    summary = asyncio.run(seed_demo_learner(replace=args.replace))
    if not args.show_credentials:
        summary.pop("password", None)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
