from pathlib import Path

import requests
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "app.py"


def login(username: str, password: str) -> dict:
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def role_app(username: str, password: str, page: str) -> AppTest:
    auth = login(username, password)
    app = AppTest.from_file(APP).run(timeout=20)
    app.session_state["access_token"] = auth["access_token"]
    app.session_state["user"] = auth["user"]
    app.session_state["page"] = page
    app.run(timeout=30)
    assert not app.exception
    return app


def main() -> None:
    taker = role_app("taker1", "taker1", "taker_dashboard")
    taker_labels = [button.label for button in taker.button]
    assert "Progress" in taker_labels
    assert "Start test" in taker_labels

    supervisor = role_app("supervisor", "supervisor", "supervisor")
    supervisor_labels = [button.label for button in supervisor.button]
    assert "Taker overview" in supervisor_labels
    assert "Exam configuration" in supervisor_labels

    admin = role_app("admin", "admin", "admin")
    admin_labels = [button.label for button in admin.button]
    assert "System overview" in admin_labels
    assert "Question bank" in admin_labels
    assert "Accounts" in admin_labels

    for page in ("admin_questions", "admin_config", "admin_accounts", "calibration"):
        admin.session_state["page"] = page
        admin.run(timeout=30)
        assert not admin.exception

    print(
        {
            "taker_page": "passed",
            "supervisor_page": "passed",
            "admin_pages": "passed",
            "role_navigation": "passed",
        }
    )


if __name__ == "__main__":
    main()
