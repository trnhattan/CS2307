import pytest

from backend.auth.errors import AuthenticationError
from backend.auth.passwords import hash_password, verify_password
from backend.auth.tokens import create_access_token, decode_access_token


def test_password_hash_round_trip() -> None:
    stored = hash_password("correct-password", salt="test-salt")

    assert verify_password("correct-password", stored)
    assert not verify_password("wrong-password", stored)
    assert "correct-password" not in stored


def test_signed_token_round_trip() -> None:
    token = create_access_token(
        {"user_id": 1, "username": "taker1", "role": "exam_taker"},
        secret="test-secret",
        ttl_minutes=5,
    )

    payload = decode_access_token(token, secret="test-secret")
    assert payload["username"] == "taker1"
    assert payload["role"] == "exam_taker"


def test_rejects_tampered_token() -> None:
    token = create_access_token(
        {"user_id": 1, "username": "admin", "role": "admin"},
        secret="test-secret",
        ttl_minutes=5,
    )
    payload, signature = token.split(".")

    with pytest.raises(AuthenticationError):
        decode_access_token(f"{payload}.{signature[:-1]}x", secret="test-secret")
