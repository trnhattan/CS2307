import base64
import hashlib
import hmac
import secrets


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 310_000


def hash_password(password: str, *, salt: str | None = None) -> str:
    password_salt = salt or secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt.encode("utf-8"),
        ITERATIONS,
    )
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{ALGORITHM}${ITERATIONS}${password_salt}${encoded}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, _ = stored_hash.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        expected = hash_password_with_iterations(password, salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, stored_hash)


def hash_password_with_iterations(password: str, salt: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{ALGORITHM}${iterations}${salt}${encoded}"
