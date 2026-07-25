import asyncio
from pathlib import Path

import asyncpg
import uvicorn

from backend.core.config import get_settings


ROOT = Path(__file__).resolve().parents[1]


async def migrate() -> None:
    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(url)
    try:
        exists = await connection.fetchval("SELECT to_regclass('public.questions')")
        if exists is None:
            await connection.execute(
                (ROOT / "scripts" / "adaptive_exam_schema_optimized.sql").read_text(
                    encoding="utf-8"
                )
            )
        await connection.execute(
            (ROOT / "scripts" / "migrate_mandatory_non_llm.sql").read_text(
                encoding="utf-8"
            )
        )
        await connection.execute(
            (ROOT / "scripts" / "migrate_calibration_and_english.sql").read_text(
                encoding="utf-8"
            )
        )
    finally:
        await connection.close()


def main() -> None:
    settings = get_settings()
    asyncio.run(migrate())
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
    )


if __name__ == "__main__":
    main()
