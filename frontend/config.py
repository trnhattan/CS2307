import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True, slots=True)
class FrontendSettings:
    host: str
    port: int
    api_base_url: str
    api_request_timeout_seconds: float


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    return FrontendSettings(
        host=os.getenv("FRONTEND_HOST", "0.0.0.0"),
        port=int(os.getenv("FRONTEND_PORT", "8501")),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/"),
        api_request_timeout_seconds=float(
            os.getenv("API_REQUEST_TIMEOUT_SECONDS", "180")
        ),
    )
