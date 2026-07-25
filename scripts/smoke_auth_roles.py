from fastapi.testclient import TestClient

from backend.main import app


ACCOUNTS = {
    "admin": "admin",
    "supervisor": "supervisor",
    "taker1": "taker1",
    "taker2": "taker2",
}


def main() -> None:
    with TestClient(app) as client:
        tokens = {}
        for username, password in ACCOUNTS.items():
            response = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": password},
            )
            response.raise_for_status()
            tokens[username] = response.json()["access_token"]

        admin_dashboard = get(client, tokens["admin"], "/api/v1/admin/dashboard")
        supervisor_dashboard = get(
            client,
            tokens["supervisor"],
            "/api/v1/supervisor/dashboard",
        )
        assert admin_dashboard.status_code == 200
        assert supervisor_dashboard.status_code == 200
        assert len(admin_dashboard.json()["accounts"]) == 4
        assert "sessions" in supervisor_dashboard.json()
        assert request(client, tokens["supervisor"], "/api/v1/admin/dashboard") == 403
        assert request(client, tokens["taker1"], "/api/v1/exams/subjects") == 200
        assert request(client, tokens["taker1"], "/api/v1/supervisor/dashboard") == 403
        summary = supervisor_dashboard.json()["summary"]
        print(
            {
                "accounts": list(tokens),
                "role_checks": "passed",
                "sessions_visible": summary["total_sessions"],
                "completed_visible": summary["completed_sessions"],
            }
        )


def request(client: TestClient, token: str, path: str) -> int:
    response = get(client, token, path)
    return response.status_code


def get(client: TestClient, token: str, path: str):
    return client.get(path, headers={"Authorization": f"Bearer {token}"})


if __name__ == "__main__":
    main()
