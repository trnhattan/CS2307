import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    backend_host: str
    backend_port: int
    database_url: str
    question_bundle_schema_path: Path
    max_upload_bytes: int
    max_line_bytes: int
    max_import_lines: int
    auth_secret: str
    auth_token_ttl_minutes: int
    llm_base_url: str
    llm_api_key: str | None
    llm_timeout_seconds: float


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
        backend_host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        backend_port=int(os.getenv("BACKEND_PORT", "8000")),
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
        llm_base_url=os.getenv("LLM_BASE_URL", "https://llm.vlai.space/v1").rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY") or None,
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
    )
