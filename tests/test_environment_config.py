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
        "LLM_BASE_URL",
        "LLM_API_KEY",
    }
    exam_keys = {
        "DEFAULT_EXAM_QUESTION_COUNT",
        "ANSWER_POOL_SIZE_BY_BLOOM",
        "CAT_MIN_QUESTION_COUNT",
        "CAT_DIFFICULTY_DISTRIBUTION",
        "IRT_SCALE_CONSTANT",
        "LLM_MODEL",
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
    assert backend.llm_base_url.endswith("/v1")
    assert backend.llm_api_key
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


def test_infrastructure_compose_does_not_receive_application_secrets() -> None:
    compose = (ROOT / "docker" / "docker-compose.yaml").read_text()

    assert "backend:" not in compose
    assert "frontend:" not in compose
    assert "build:" not in compose
    assert "env_file:" not in compose
    assert "LLM_API_KEY" not in compose
