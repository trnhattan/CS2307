from typing import Any

import requests

from frontend.config import get_frontend_settings


class APIClientError(RuntimeError):
    pass


class ExamAPIClient:
    def __init__(self, token: str | None = None) -> None:
        settings = get_frontend_settings()
        self.base_url = settings.api_base_url
        self.timeout_seconds = settings.api_request_timeout_seconds
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

    def start_cat(self, subject_code: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/cat/start",
            json={"subject_code": subject_code},
        )

    def answer_cat(
        self,
        session_id: int,
        exam_item_id: int,
        option_code: str,
        response_time_sec: int,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/cat/{session_id}/answer",
            json={
                "exam_item_id": exam_item_id,
                "selected_option_code": option_code,
                "response_time_sec": response_time_sec,
            },
        )

    def cat_result(self, session_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/cat/{session_id}/result")

    def staff_cat(self, session_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/supervisor/cat/{session_id}")

    def taker_knowledge_graph(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/taker/knowledge-graph")

    def staff_knowledge_graph(self, student_id: int) -> dict[str, Any]:
        return self._request(
            "GET", f"/api/v1/students/{student_id}/knowledge-graph"
        )

    def generation_status(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/generation/status")

    def generation_catalog(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/generation/catalog")

    def recent_generations(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/generation/recent")

    def generate_question_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/generation/questions", json=payload)

    def staff_exam_explanation(
        self, session_id: int, refresh: bool = False
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/explanations/sessions/{session_id}",
            params={"refresh": str(refresh).lower()},
        )

    def taker_exam_explanation(
        self, session_id: int, refresh: bool = False
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/taker/explanations/{session_id}",
            params={"refresh": str(refresh).lower()},
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

    def cat_config(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/supervisor/config/cat")

    def update_cat_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "PUT", "/api/v1/supervisor/config/cat", json=payload
        )

    def admin_dashboard(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/dashboard")

    def admin_overview(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/overview")

    def admin_questions(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/questions")

    def question_readiness(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/admin/questions/readiness")

    def admin_question(self, question_code: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/admin/questions/{question_code}")

    def update_admin_question(
        self, question_code: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/v1/admin/questions/{question_code}",
            json=payload,
        )

    def review_question(self, question_code: str) -> dict[str, Any]:
        return self._request(
            "POST", f"/api/v1/admin/questions/{question_code}/review"
        )

    def activate_question(self, question_code: str) -> dict[str, Any]:
        return self._request(
            "POST", f"/api/v1/admin/questions/{question_code}/activate"
        )

    def bulk_activate_questions(self, question_codes: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/admin/questions/bulk-activate",
            json={"question_codes": question_codes},
        )

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
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as error:
            raise APIClientError(
                f"Không thể kết nối backend tại {self.base_url}."
            ) from error

        if response.ok:
            return response.json()
        try:
            detail = response.json().get("detail", response.text)
        except requests.JSONDecodeError:
            detail = response.text
        raise APIClientError(str(detail))
