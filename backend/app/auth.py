"""Single-account sign-in: password hashing and signed tokens.

Standard library only. Nothing here writes a password, a hash or a token to a
log, and no credential is ever hard-coded: every value comes from settings.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import settings

PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16
DEFAULT_TOKEN_HOURS = 12

NOT_CONFIGURED_MESSAGE = (
    "Sign-in is not configured. Set AXIOM_USERNAME, AXIOM_PASSWORD_HASH and "
    "AXIOM_SECRET in backend/.env."
)


class AuthError(Exception):
    """A token that cannot be trusted: malformed, badly signed or expired."""


class AuthNotConfigured(AuthError):
    """Sign-in was attempted while the account settings are missing."""


def is_configured() -> bool:
    """True when a username, a password hash and a secret are all present."""
    return bool(
        settings.axiom_username and settings.axiom_password_hash and settings.axiom_secret
    )


def _secret() -> str:
    secret = settings.axiom_secret
    if not secret:
        raise AuthNotConfigured(NOT_CONFIGURED_MESSAGE)
    return secret


def token_hours() -> int:
    hours = settings.axiom_token_hours
    return hours if isinstance(hours, int) and hours > 0 else DEFAULT_TOKEN_HOURS


# --- passwords ---------------------------------------------------------------


def hash_password(
    password: str,
    iterations: int = PBKDF2_ITERATIONS,
    salt: Optional[bytes] = None,
) -> str:
    """Return "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>"."""
    if iterations < 200_000:
        raise ValueError("PBKDF2 needs at least 200000 iterations.")
    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "{scheme}${iterations}${salt}${digest}".format(
        scheme=PBKDF2_SCHEME,
        iterations=iterations,
        salt=salt.hex(),
        digest=digest.hex(),
    )


def verify_password(password: str, stored: str) -> bool:
    """Compare a password with a stored hash in constant time."""
    if not stored:
        return False
    try:
        scheme, iteration_text, salt_hex, digest_hex = stored.split("$")
        if scheme != PBKDF2_SCHEME:
            return False
        iterations = int(iteration_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False

    if iterations < 1 or not salt or not expected:
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


# --- tokens ------------------------------------------------------------------


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(encoded_payload: str, secret: str) -> str:
    return _b64encode(
        hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    )


def token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=token_hours())


def issue_token(username: str) -> str:
    """Return "payload.signature" for this username."""
    secret = _secret()
    payload = {
        "sub": username,
        "exp": int(token_expiry().timestamp()),
        "iat": int(time.time()),
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return "{}.{}".format(encoded, _sign(encoded, secret))


def read_token(token: str) -> str:
    """Return the username in a valid token, or raise AuthError."""
    secret = _secret()

    if not isinstance(token, str) or token.count(".") != 1:
        raise AuthError("Malformed token.")

    encoded, signature = token.split(".")
    if not encoded or not signature:
        raise AuthError("Malformed token.")

    try:
        expected = _sign(encoded, secret)
        supplied = signature
    except (UnicodeEncodeError, ValueError):
        raise AuthError("Malformed token.")

    # Check the signature before looking at the payload at all.
    if not hmac.compare_digest(expected, supplied):
        raise AuthError("Invalid token signature.")

    try:
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise AuthError("Malformed token.")

    if not isinstance(payload, dict):
        raise AuthError("Malformed token.")

    username = payload.get("sub")
    expires_at = payload.get("exp")

    if not isinstance(username, str) or not username:
        raise AuthError("Malformed token.")
    if not isinstance(expires_at, int):
        raise AuthError("Malformed token.")
    if expires_at <= int(time.time()):
        raise AuthError("Token has expired.")

    # One local account: a token for any other name is not usable here.
    if username != settings.axiom_username:
        raise AuthError("Token is not valid for this account.")

    return username
