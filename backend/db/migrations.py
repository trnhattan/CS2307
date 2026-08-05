import logging
from pathlib import Path

import asyncpg

from backend.core.config import get_settings


logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_FILES = (
    "migrate_mandatory_non_llm.sql",
    "migrate_calibration_and_english.sql",
    "migrate_learner_model.sql",
    "migrate_openrouter.sql",
    "migrate_gemini.sql",
)


async def apply_migrations() -> None:
    settings = get_settings()
    database_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    connection = await asyncpg.connect(database_url)
    try:
        exists = await connection.fetchval("SELECT to_regclass('public.questions')")
        if exists is None:
            await connection.execute(
                (ROOT / "scripts" / "adaptive_exam_schema_optimized.sql").read_text(
                    encoding="utf-8"
                )
            )
        for filename in MIGRATION_FILES:
            await connection.execute(
                (ROOT / "scripts" / filename).read_text(encoding="utf-8")
            )
    finally:
        await connection.close()
    logger.info("Database migrations are up to date")
