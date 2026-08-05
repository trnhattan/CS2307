from pathlib import Path

from backend.core.config import get_settings
from frontend.config import get_frontend_settings


ROOT = Path(__file__).resolve().parents[1]


def _keys(path: Path) -> set[str]:
    return {
        line.split("=", 1)[0].strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }


def test_environment_files_define_only_runtime_and_secret_configuration() -> None:
    expected = {
        "BACKEND_HOST",
        "BACKEND_PORT",
        "FRONTEND_HOST",
        "FRONTEND_PORT",
        "API_BASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "AUTH_SECRET",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_HTTP_REFERER",
        "OPENROUTER_APP_TITLE",
        "GEMINI_BASE_URL",
        "GEMINI_API_KEY",
        "GEMINI_THINKING_LEVEL",
    }
    exam_keys = {
        "DEFAULT_EXAM_QUESTION_COUNT",
        "ANSWER_POOL_SIZE_BY_BLOOM",
        "CAT_MIN_QUESTION_COUNT",
        "CAT_DIFFICULTY_DISTRIBUTION",
        "IRT_SCALE_CONSTANT",
        "LLM_MODEL",
        "LLM_REASONING_ENABLED",
        "LLM_QUESTION_MAX_TOKENS",
        "LLM_TEMPERATURE",
    }

    for filename in (".env", ".env.example"):
        keys = _keys(ROOT / filename)
        assert expected <= keys
        assert not keys & exam_keys


def test_backend_and_frontend_load_shared_environment() -> None:
    backend = get_settings()
    frontend = get_frontend_settings()

    assert backend.backend_port == 8000
    assert backend.database_url.startswith("postgresql+asyncpg://")
    assert backend.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert backend.openrouter_api_key is None or backend.openrouter_api_key
    assert backend.gemini_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert backend.gemini_api_key is None or backend.gemini_api_key
    assert frontend.port == 8501
    assert frontend.api_base_url == "http://localhost:8000"


def test_exam_behavior_is_seeded_in_sys_props_not_env() -> None:
    schema = (ROOT / "scripts" / "adaptive_exam_schema_optimized.sql").read_text()

    for key in (
        "DEFAULT_EXAM_QUESTION_COUNT",
        "ANSWER_POOL_SIZE_BY_BLOOM",
        "CAT_MIN_QUESTION_COUNT",
        "CAT_DIFFICULTY_DISTRIBUTION",
        "IRT_SCALE_CONSTANT",
        "LLM_MODEL",
        "LLM_REASONING_ENABLED",
        "LLM_QUESTION_MAX_TOKENS",
        "LLM_TEMPERATURE",
    ):
        assert f"('{key}'" in schema


def test_launchers_use_loaded_host_and_port() -> None:
    backend = (ROOT / "scripts" / "start_backend.py").read_text()
    frontend = (ROOT / "scripts" / "start_frontend.py").read_text()

    assert "settings.backend_host" in backend
    assert "settings.backend_port" in backend
    assert "settings.host" in frontend
    assert "settings.port" in frontend


def test_compose_containerizes_app_without_baking_secrets() -> None:
    compose = (ROOT / "docker" / "docker-compose.yaml").read_text()
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text()
    dockerignore = (ROOT / ".dockerignore").read_text()

    assert "  backend:" in compose
    assert "  frontend:" in compose
    assert "target: backend" in compose
    assert "target: frontend" in compose
    assert "@postgres:5432/" in compose
    assert "API_BASE_URL: http://backend:8000" in compose
    assert compose.count("condition: service_healthy") >= 2
    assert "OPENROUTER_API_KEY:" not in compose
    assert "FROM runtime AS backend" in dockerfile
    assert "FROM runtime AS frontend" in dockerfile
    assert dockerfile.count("USER app") == 2
    assert ".env" in dockerignore
