"""Password hashing (PBKDF2-SHA256 from the standard library) and CSRF helpers."""
import base64
import hashlib
import hmac
import os
import secrets

DEFAULT_ITERATIONS = 200_000


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or int(os.getenv("PASSWORD_ITERATIONS", DEFAULT_ITERATIONS))
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, base64.b64encode(salt).decode(), base64.b64encode(digest).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_matches(session_token: str | None, submitted: str | None) -> bool:
    if not session_token or not submitted:
        return False
    return hmac.compare_digest(session_token, submitted)
