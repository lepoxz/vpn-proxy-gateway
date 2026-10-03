"""Encryption, secret generation and authentication helpers."""

import hmac
import json
import secrets
import string
import threading
import time
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.fernet import Fernet, InvalidToken

_ALPHABET = string.ascii_letters + string.digits


class Vault:
    """Symmetric encryption for secrets stored in the database."""

    def __init__(self, master_key: str):
        self._fernet = Fernet(master_key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:  # pragma: no cover - indicates wrong master key
            raise RuntimeError("Cannot decrypt secret: wrong VPG_MASTER_KEY?") from exc

    def encrypt_json(self, data: dict) -> str:
        return self.encrypt(json.dumps(data))

    def decrypt_json(self, token: str) -> dict:
        return json.loads(self.decrypt(token))


def random_secret(length: int = 24) -> str:
    """URL-safe alphanumeric secret (no characters that need escaping in proxy URLs)."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# --- Sessions ----------------------------------------------------------------


def issue_session(secret: str, username: str, ttl_hours: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": username, "iat": now, "exp": now + timedelta(hours=ttl_hours)}
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_session(secret: str, token: str) -> str | None:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


# --- Login rate limiting -------------------------------------------------------


class LoginThrottle:
    """Lock out a client IP after too many failed logins within a window."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 900):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._failures.get(key, []) if now - t < self.window]
        self._failures[key] = recent
        return recent

    def is_locked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_failures

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
