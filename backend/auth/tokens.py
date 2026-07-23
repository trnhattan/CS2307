import base64
import hashlib
import hmac
import json
import time
from typing import Any

from backend.auth.errors import AuthenticationError


def create_access_token(
    payload: dict[str, Any],
    *,
    secret: str,
    ttl_minutes: int,
) -> str:
    claims = dict(payload)
    claims["exp"] = int(time.time()) + ttl_minutes * 60
    encoded = _encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256)
    return f"{encoded}.{_encode(signature.digest())}"


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    try:
        encoded, provided_signature = token.split(".", 1)
        expected = hmac.new(
            secret.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        )
        if not hmac.compare_digest(_encode(expected.digest()), provided_signature):
            raise AuthenticationError("Invalid access token")
        payload = json.loads(_decode(encoded))
        if int(payload["exp"]) < int(time.time()):
            raise AuthenticationError("Access token has expired")
        return payload
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        raise AuthenticationError("Invalid access token") from error


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
