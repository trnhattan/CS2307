import json

from fastapi.testclient import TestClient

from backend.main import app


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    with TestClient(app) as client:
        taker_token = login(client, "taker1", "taker1")
        supervisor_token = login(client, "supervisor", "supervisor")
        admin_token = login(client, "admin", "admin")

        taker = client.get(
            "/api/v1/taker/dashboard",
            headers=headers(taker_token),
        )
        taker.raise_for_status()
        taker_text = json.dumps(taker.json()).lower()
        assert all(value not in taker_text for value in ("theta", "bloom", "fisher"))

        supervisor = client.get(
            "/api/v1/supervisor/dashboard",
            headers=headers(supervisor_token),
        )
        supervisor.raise_for_status()
        assert len(supervisor.json()["takers"]) >= 2

        difficulty = client.get(
            "/api/v1/supervisor/config/difficulty-distribution",
            headers=headers(supervisor_token),
        )
        difficulty.raise_for_status()
        updated = client.put(
            "/api/v1/supervisor/config/difficulty-distribution",
            json=difficulty.json()["distribution"],
            headers=headers(supervisor_token),
        )
        updated.raise_for_status()

        overview = client.get(
            "/api/v1/admin/overview",
            headers=headers(admin_token),
        )
        overview.raise_for_status()
        questions = client.get(
            "/api/v1/admin/questions",
            headers=headers(admin_token),
        )
        questions.raise_for_status()
        config = client.get(
            "/api/v1/admin/config",
            headers=headers(admin_token),
        )
        config.raise_for_status()
        accounts = client.get(
            "/api/v1/admin/accounts",
            headers=headers(admin_token),
        )
        accounts.raise_for_status()
        taker2 = next(item for item in accounts.json() if item["username"] == "taker2")
        account_update = client.patch(
            "/api/v1/admin/accounts/taker2",
            json={
                "display_name": taker2["display_name"],
                "is_active": taker2["is_active"],
            },
            headers=headers(admin_token),
        )
        account_update.raise_for_status()

        assert client.get(
            "/api/v1/admin/overview",
            headers=headers(supervisor_token),
        ).status_code == 403
        assert client.get(
            "/api/v1/supervisor/dashboard",
            headers=headers(taker_token),
        ).status_code == 403

        print(
            {
                "taker_tests": taker.json()["summary"]["completed_tests"],
                "learning_steps": len(taker.json()["learning_path"]),
                "supervisor_takers": len(supervisor.json()["takers"]),
                "question_bank": questions.json()["total_questions"],
                "config_items": len(config.json()["items"]),
                "accounts": len(accounts.json()),
                "role_checks": "passed",
            }
        )


if __name__ == "__main__":
    main()
