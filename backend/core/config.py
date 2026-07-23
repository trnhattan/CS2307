import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    database_url: str
    question_bundle_schema_path: Path
    max_upload_bytes: int
    max_line_bytes: int
    max_import_lines: int
    auth_secret: str
    auth_token_ttl_minutes: int


@lru_cache
def get_settings() -> Settings:
    schema_path = Path(
        os.getenv(
            "QUESTION_BUNDLE_SCHEMA_PATH",
            "scripts/adaptive_exam_question_bundle.schema.json",
        )
    )
    if not schema_path.is_absolute():
        schema_path = PROJECT_ROOT / schema_path

    return Settings(
        app_name=os.getenv("APP_NAME", "Adaptive Exam API"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/app",
        ),
        question_bundle_schema_path=schema_path,
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        max_line_bytes=int(os.getenv("MAX_LINE_BYTES", str(2 * 1024 * 1024))),
        max_import_lines=int(os.getenv("MAX_IMPORT_LINES", "5000")),
        auth_secret=os.getenv(
            "AUTH_SECRET",
            "cs2307-local-development-secret-change-before-deployment",
        ),
        auth_token_ttl_minutes=int(os.getenv("AUTH_TOKEN_TTL_MINUTES", "480")),
    )
