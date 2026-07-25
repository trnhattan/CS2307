from fastapi.testclient import TestClient

from backend.main import app


def main() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "taker1", "password": "taker1"},
        )
        login.raise_for_status()
        headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }
        generated = client.post(
            "/api/v1/exams/generate",
            json={
                "subject_codes": ["DATABASE"],
                "question_count": 5,
                "seed": 2307,
            },
            headers=headers,
        )
        generated.raise_for_status()
        exam = generated.json()["sessions"][0]
        assert "theta_initial" not in exam
        assert "bloom_level" not in exam["questions"][0]
        assert "selection_reason" not in exam["questions"][0]
        answers = [
            {
                "exam_item_id": question["exam_item_id"],
                "selected_option_code": question["options"][0]["option_code"],
                "response_time_sec": 30,
            }
            for question in exam["questions"]
        ]
        submitted = client.post(
            f"/api/v1/exams/{exam['session_id']}/submit",
            json={"answers": answers},
            headers=headers,
        )
        submitted.raise_for_status()
        result = submitted.json()
        assert "theta_after" not in result
        assert "standard_error" not in result
        assert "mastery_probability" not in result
        assert result["feedback"][0]["stem"] == exam["questions"][0]["stem"]
        print(
            {
                "session_id": exam["session_id"],
                "questions": len(exam["questions"]),
                "score": result["total_score"],
                "percentage": result["percentage"],
                "understanding": result["understanding_label"],
            }
        )


if __name__ == "__main__":
    main()
