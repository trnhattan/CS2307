import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.questions.errors import DatabaseContractError


class QuestionBundleRepository:
    async def upsert_bundle(
        self,
        session: AsyncSession,
        bundle: dict[str, Any],
    ) -> str:
        subject_id = await self._upsert_subject(session, bundle["subject"])
        topic_id = await self._upsert_topic(
            session,
            subject_id,
            bundle["topic"],
        )
        skill_ids = [
            (
                await self._upsert_knowledge_unit(
                    session,
                    subject_id=subject_id,
                    parent_unit_id=None,
                    code=skill["skill_code"],
                    name=skill["skill_name"],
                    unit_type="skill",
                    description=skill.get("description"),
                    is_active=True,
                ),
                skill,
            )
            for skill in bundle["skills"]
        ]
        await self._ensure_predicates(session, bundle["kb_facts"])
        question_id, operation = await self._upsert_question(
            session,
            subject_id,
            bundle,
        )
        await self._replace_options(session, question_id, bundle["answer_options"])
        await self._replace_question_units(
            session,
            question_id,
            topic_id,
            skill_ids,
        )
        await self._upsert_facts(session, bundle["kb_facts"])
        return operation

    async def _upsert_subject(
        self,
        session: AsyncSession,
        subject: dict[str, Any],
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO subjects (
                    subject_code, subject_name, description, is_active
                )
                VALUES (
                    :subject_code, :subject_name, :description, :is_active
                )
                ON CONFLICT (subject_code) DO UPDATE SET
                    subject_name = EXCLUDED.subject_name,
                    description = EXCLUDED.description,
                    is_active = EXCLUDED.is_active
                RETURNING subject_id
                """
            ),
            {
                "subject_code": subject["subject_code"],
                "subject_name": subject["subject_name"],
                "description": subject.get("description"),
                "is_active": subject.get("is_active", True),
            },
        )
        return result.scalar_one()

    async def _upsert_topic(
        self,
        session: AsyncSession,
        subject_id: int,
        topic: dict[str, Any],
    ) -> int:
        parent_id = None
        parent_code = topic.get("parent_topic_code")
        if parent_code:
            result = await session.execute(
                text(
                    """
                    SELECT unit_id
                    FROM knowledge_units
                    WHERE subject_id = :subject_id
                      AND unit_code = :unit_code
                      AND unit_type = 'topic'
                    """
                ),
                {"subject_id": subject_id, "unit_code": parent_code},
            )
            parent_id = result.scalar_one_or_none()
            if parent_id is None:
                raise DatabaseContractError(
                    f"Parent topic '{parent_code}' does not exist for this subject"
                )

        return await self._upsert_knowledge_unit(
            session,
            subject_id=subject_id,
            parent_unit_id=parent_id,
            code=topic["topic_code"],
            name=topic["topic_name"],
            unit_type="topic",
            description=topic.get("description"),
            is_active=topic.get("is_active", True),
        )

    async def _upsert_knowledge_unit(
        self,
        session: AsyncSession,
        *,
        subject_id: int,
        parent_unit_id: int | None,
        code: str,
        name: str,
        unit_type: str,
        description: str | None,
        is_active: bool,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO knowledge_units (
                    subject_id, parent_unit_id, unit_code, unit_name,
                    unit_type, description, is_active
                )
                VALUES (
                    :subject_id, :parent_unit_id, :unit_code, :unit_name,
                    :unit_type, :description, :is_active
                )
                ON CONFLICT (subject_id, unit_code) DO UPDATE SET
                    parent_unit_id = EXCLUDED.parent_unit_id,
                    unit_name = EXCLUDED.unit_name,
                    description = EXCLUDED.description,
                    is_active = EXCLUDED.is_active
                WHERE knowledge_units.unit_type = EXCLUDED.unit_type
                RETURNING unit_id
                """
            ),
            {
                "subject_id": subject_id,
                "parent_unit_id": parent_unit_id,
                "unit_code": code,
                "unit_name": name,
                "unit_type": unit_type,
                "description": description,
                "is_active": is_active,
            },
        )
        unit_id = result.scalar_one_or_none()
        if unit_id is None:
            raise DatabaseContractError(
                f"Knowledge unit '{code}' already exists with a different type"
            )
        return unit_id

    async def _ensure_predicates(
        self,
        session: AsyncSession,
        facts: list[dict[str, Any]],
    ) -> None:
        predicates = sorted(
            {fact.get("relation_code") or fact["predicate"] for fact in facts}
        )
        result = await session.execute(
            text(
                """
                SELECT definition_code
                FROM kb_definitions
                WHERE definition_code = ANY(CAST(:codes AS VARCHAR[]))
                """
            ),
            {"codes": predicates},
        )
        existing = set(result.scalars())
        missing = sorted(set(predicates) - existing)
        if missing:
            raise DatabaseContractError(
                f"Unknown knowledge-base predicate(s): {', '.join(missing)}"
            )

    async def _upsert_question(
        self,
        session: AsyncSession,
        subject_id: int,
        bundle: dict[str, Any],
    ) -> tuple[int, str]:
        question = bundle["question"]
        irt_item = bundle["irt_item"]
        existing_result = await session.execute(
            text(
                """
                SELECT question_id, version_no
                FROM questions
                WHERE question_code = :code
                """
            ),
            {"code": question["question_code"]},
        )
        existing = existing_result.one_or_none()
        if existing and question["version_no"] < existing.version_no:
            raise DatabaseContractError(
                f"Incoming version {question['version_no']} is older than stored "
                f"version {existing.version_no}"
            )
        provenance = dict(question["provenance"])
        provenance["ingest"] = {
            "schema_version": bundle["schema_version"],
            "difficulty_norm": irt_item["difficulty_norm"],
            "irt_provenance": irt_item["provenance"],
        }
        if irt_item.get("calibrated_at"):
            provenance["ingest"]["calibrated_at"] = irt_item["calibrated_at"]

        result = await session.execute(
            text(
                """
                INSERT INTO questions (
                    question_code, subject_id, stem, question_type, scoring_mode,
                    bloom_level, difficulty_label, difficulty_norm, avg_time_sec, explanation,
                    display_option_count, must_include_best, randomize_options,
                    irt_a, irt_b, irt_c, irt_status, irt_sample_size,
                    irt_model_version, status, source, created_by, reviewed_by,
                    reviewed_at, provenance, version_no
                )
                VALUES (
                    :question_code, :subject_id, :stem, :question_type, :scoring_mode,
                    :bloom_level, :difficulty_label, :difficulty_norm, :avg_time_sec, :explanation,
                    :display_option_count, :must_include_best, :randomize_options,
                    :irt_a, :irt_b, :irt_c, :irt_status, :irt_sample_size,
                    :irt_model_version, :status, :source, :created_by, :reviewed_by,
                    CAST(:reviewed_at AS TIMESTAMPTZ), CAST(:provenance AS JSONB),
                    :version_no
                )
                ON CONFLICT (question_code) DO UPDATE SET
                    subject_id = EXCLUDED.subject_id,
                    stem = EXCLUDED.stem,
                    question_type = EXCLUDED.question_type,
                    scoring_mode = EXCLUDED.scoring_mode,
                    bloom_level = EXCLUDED.bloom_level,
                    difficulty_label = EXCLUDED.difficulty_label,
                    difficulty_norm = EXCLUDED.difficulty_norm,
                    avg_time_sec = EXCLUDED.avg_time_sec,
                    explanation = EXCLUDED.explanation,
                    display_option_count = EXCLUDED.display_option_count,
                    must_include_best = EXCLUDED.must_include_best,
                    randomize_options = EXCLUDED.randomize_options,
                    irt_a = EXCLUDED.irt_a,
                    irt_b = EXCLUDED.irt_b,
                    irt_c = EXCLUDED.irt_c,
                    irt_status = EXCLUDED.irt_status,
                    irt_sample_size = EXCLUDED.irt_sample_size,
                    irt_model_version = EXCLUDED.irt_model_version,
                    status = 'draft',
                    source = EXCLUDED.source,
                    created_by = EXCLUDED.created_by,
                    reviewed_by = EXCLUDED.reviewed_by,
                    reviewed_at = EXCLUDED.reviewed_at,
                    provenance = EXCLUDED.provenance,
                    version_no = EXCLUDED.version_no
                RETURNING question_id
                """
            ),
            {
                "question_code": question["question_code"],
                "subject_id": subject_id,
                "stem": question["stem"],
                "question_type": question["question_type"],
                "scoring_mode": question["scoring_mode"],
                "bloom_level": bundle["bloom"]["bloom_code"],
                "difficulty_label": question["difficulty_label"],
                "difficulty_norm": irt_item["difficulty_norm"],
                "avg_time_sec": question["avg_time_sec"],
                "explanation": question["explanation"],
                "display_option_count": question["display_option_count"],
                "must_include_best": question["must_include_best"],
                "randomize_options": question["randomize_options"],
                "irt_a": irt_item["a_discrimination"],
                "irt_b": irt_item["b_difficulty"],
                "irt_c": irt_item["c_guessing"],
                "irt_status": irt_item["calibrated_status"],
                "irt_sample_size": irt_item["calibration_sample_size"],
                "irt_model_version": irt_item["model_version"],
                "status": "draft",
                "source": question["source"],
                "created_by": question["created_by"],
                "reviewed_by": question.get("reviewed_by"),
                "reviewed_at": question.get("reviewed_at"),
                "provenance": self._json(provenance),
                "version_no": question["version_no"],
            },
        )
        return result.scalar_one(), "updated" if existing else "created"

    async def _replace_options(
        self,
        session: AsyncSession,
        question_id: int,
        options: list[dict[str, Any]],
    ) -> None:
        await session.execute(
            text("DELETE FROM answer_options WHERE question_id = :question_id"),
            {"question_id": question_id},
        )
        statement = text(
            """
            INSERT INTO answer_options (
                question_id, option_code, option_text, score_weight,
                is_best_answer, distractor_type, misconception_code, diagnosis,
                explanation, is_active, source, provenance
            )
            VALUES (
                :question_id, :option_code, :option_text, :score_weight,
                :is_best_answer, :distractor_type, :misconception_code, :diagnosis,
                :explanation, :is_active, :source, CAST(:provenance AS JSONB)
            )
            """
        )
        await session.execute(
            statement,
            [
                {
                    "question_id": question_id,
                    "option_code": option["option_code"],
                    "option_text": option["option_text"],
                    "score_weight": option["score_weight"],
                    "is_best_answer": option["is_best_answer"],
                    "distractor_type": option["distractor_level"],
                    "misconception_code": option.get("misconception_code"),
                    "diagnosis": option.get("diagnosis"),
                    "explanation": option.get("explanation"),
                    "is_active": option.get("is_active", True),
                    "source": option["source"],
                    "provenance": self._json(option.get("provenance", {})),
                }
                for option in options
            ],
        )

    async def _replace_question_units(
        self,
        session: AsyncSession,
        question_id: int,
        topic_id: int,
        skill_ids: list[tuple[int, dict[str, Any]]],
    ) -> None:
        await session.execute(
            text(
                "DELETE FROM question_knowledge_units WHERE question_id = :question_id"
            ),
            {"question_id": question_id},
        )
        rows = [
            {
                "question_id": question_id,
                "unit_id": topic_id,
                "unit_role": "topic",
                "measurement_weight": 1,
            }
        ]
        rows.extend(
            {
                "question_id": question_id,
                "unit_id": unit_id,
                "unit_role": (
                    "primary_skill" if skill["is_primary"] else "supporting_skill"
                ),
                "measurement_weight": skill["measurement_weight"],
            }
            for unit_id, skill in skill_ids
        )
        await session.execute(
            text(
                """
                INSERT INTO question_knowledge_units (
                    question_id, unit_id, unit_role, measurement_weight
                )
                VALUES (
                    :question_id, :unit_id, :unit_role, :measurement_weight
                )
                """
            ),
            rows,
        )

    async def _upsert_facts(
        self,
        session: AsyncSession,
        facts: list[dict[str, Any]],
    ) -> None:
        statement = text(
            """
            INSERT INTO kb_facts (
                fact_type, subject_ref, predicate_code, object_ref, object_value,
                fact_args, confidence, is_inferred, source, created_by, provenance
            )
            VALUES (
                :fact_type, :subject_ref, :predicate_code, :object_ref,
                CAST(:object_value AS JSONB), CAST(:fact_args AS JSONB),
                :confidence, FALSE, :source,
                :created_by, CAST(:provenance AS JSONB)
            )
            ON CONFLICT (fact_type, predicate_code, (fact_args::TEXT))
            DO UPDATE SET
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                created_by = EXCLUDED.created_by,
                provenance = EXCLUDED.provenance
            """
        )
        rows = []
        for fact in facts:
            predicate_code = fact.get("relation_code") or fact["predicate"]
            provenance = dict(fact["provenance"])
            if predicate_code != fact["predicate"]:
                provenance["bundle_predicate"] = fact["predicate"]
            rows.append(
                {
                    "fact_type": fact["fact_type"],
                    "subject_ref": fact["subject_ref"],
                    "predicate_code": predicate_code,
                    "object_ref": fact.get("object_ref"),
                    "object_value": (
                        self._json(fact["object_value"])
                        if "object_value" in fact
                        else None
                    ),
                    "fact_args": self._json(
                        [
                            fact["subject_ref"],
                            fact.get("object_ref", fact.get("object_value")),
                        ]
                    ),
                    "confidence": fact["confidence"],
                    "source": fact["source"],
                    "created_by": fact["created_by"],
                    "provenance": self._json(provenance),
                }
            )
        await session.execute(statement, rows)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
