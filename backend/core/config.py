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
    openrouter_base_url: str
    openrouter_api_key: str | None
    openrouter_http_referer: str | None
    openrouter_app_title: str | None
    gemini_base_url: str
    gemini_api_key: str | None
    gemini_thinking_level: str
    llm_timeout_seconds: float
    mcp_issuer_url: str
    mcp_public_url: str


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
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
        openrouter_http_referer=os.getenv("OPENROUTER_HTTP_REFERER") or None,
        openrouter_app_title=os.getenv("OPENROUTER_APP_TITLE") or None,
        gemini_base_url=os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        ).rstrip("/"),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_thinking_level=os.getenv("GEMINI_THINKING_LEVEL", "low").strip().lower(),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        mcp_issuer_url=os.getenv(
            "MCP_ISSUER_URL", "http://localhost:8000"
        ).rstrip("/"),
        mcp_public_url=os.getenv(
            "MCP_PUBLIC_URL", "http://localhost:8000/mcp"
        ).rstrip("/"),
    )
