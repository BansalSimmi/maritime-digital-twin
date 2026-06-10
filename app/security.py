import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Optional


SESSION_COOKIE_NAME = "session"
SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 hours


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def get_session_secret() -> bytes:
    secret = os.environ.get("SESSION_SECRET") or os.environ.get("SECRET_KEY") or "dev-secret-change-me"
    return secret.encode("utf-8")


def create_session_token(payload: dict[str, Any], ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    now = int(time.time())
    body = dict(payload)
    body.setdefault("iat", now)
    body.setdefault("exp", now + int(ttl_seconds))

    secret = get_session_secret()
    body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_b64 = _b64url_encode(body_bytes)
    sig = hmac.new(secret, body_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{body_b64}.{sig_b64}"


def verify_session_token(token: str) -> Optional[dict[str, Any]]:
    try:
        body_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        return None

    secret = get_session_secret()
    expected_sig = hmac.new(secret, body_b64.encode("ascii"), hashlib.sha256).digest()
    expected_sig_b64 = _b64url_encode(expected_sig)
    if not hmac.compare_digest(expected_sig_b64, sig_b64):
        return None

    try:
        body = json.loads(_b64url_decode(body_b64))
    except Exception:
        return None

    now = int(time.time())
    exp = int(body.get("exp", 0) or 0)
    if exp <= now:
        return None

    return body

