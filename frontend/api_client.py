import os
from typing import Any

import requests


class APIClientError(RuntimeError):
    pass


class ExamAPIClient:
    def __init__(self, token: str | None = None) -> None:
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
        self.token = token

    def login(self, username: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            authenticated=False,
        )

    def me(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/auth/me")

    def subjects(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/exams/subjects")

    def generate(self, subject_codes: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/exams/generate",
            json={"subject_codes": subject_codes},
        )

    def submit(self, session_id: int, answers: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/exams/{session_id}/submit",
            json={"answers": answers},
        )

    def taker_dashboard(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/taker/dashboard")

    def supervisor_dashboard(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/supervisor/dashboard")

    def difficulty_config(self) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/supervisor/config/difficulty-distribution",
        )

    def update_difficulty_config(
        self,
        easy: float,
        medium: float,
        hard: float,
    ) -> dict[str, Any]:
        return self._request(
            "PUT",
            "/api/v1/supervisor/config/difficulty-distribution",
            json={"easy": easy, "medium": medium, "hard": hard},
        )

    def admin_dashboard(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/dashboard")

    def admin_overview(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/overview")

    def admin_questions(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/questions")

    def admin_config(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/config")

    def update_admin_config(self, updates: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request(
            "PUT",
            "/api/v1/admin/config",
            json={"updates": updates},
        )

    def admin_accounts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/admin/accounts")

    def create_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/admin/accounts", json=payload)

    def update_account(
        self,
        username: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/v1/admin/accounts/{username}",
            json=payload,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if authenticated:
            if not self.token:
                raise APIClientError("Phiên đăng nhập không hợp lệ.")
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=60,
                **kwargs,
            )
        except requests.RequestException as error:
            raise APIClientError(
                "Không thể kết nối backend. Hãy chạy FastAPI ở cổng 8000."
            ) from error

        if response.ok:
            return response.json()
        try:
            detail = response.json().get("detail", response.text)
        except requests.JSONDecodeError:
            detail = response.text
        raise APIClientError(str(detail))
