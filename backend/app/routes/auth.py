from __future__ import annotations

import hmac
import re
import threading
import time
from collections import deque
from typing import Deque, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    NOT_CONFIGURED_MESSAGE,
    AuthError,
    hash_password,
    is_configured,
    issue_token,
    read_token,
    token_expiry,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.models import AppUser

router = APIRouter(tags=["auth"])

# One message for every rejected sign-in: the response must not reveal whether
# the username or the password was the wrong part.
BAD_CREDENTIALS_MESSAGE = "Incorrect username or password."
SESSION_INVALID_MESSAGE = "Your session has ended. Sign in again."
USERNAME_TAKEN_MESSAGE = "That username is already taken."
TOO_MANY_ATTEMPTS_MESSAGE = "Too many attempts. Try again in a minute."

USERNAME_RULE = (
    "Username must be 3 to 32 characters: letters, digits, dot, underscore or hyphen."
)
PASSWORD_RULE = "Password must be at least 8 characters."

USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,32}$")
MIN_PASSWORD_LENGTH = 8

# Register is public, so it is capped per client address. In memory only: a
# restart clears the counters, which is fine for one local machine.
REGISTER_LIMIT = 10
REGISTER_WINDOW_SECONDS = 60

_register_attempts: Dict[str, Deque[float]] = {}
_register_lock = threading.Lock()


def reset_register_limits() -> None:
    """Forget every recorded attempt (used by the tests)."""
    with _register_lock:
        _register_attempts.clear()


def _record_register_attempt(client_host: str) -> None:
    """Count this attempt, or answer 429 once the minute is used up."""
    now = time.monotonic()
    with _register_lock:
        bucket = _register_attempts.setdefault(client_host, deque())
        while bucket and now - bucket[0] > REGISTER_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= REGISTER_LIMIT:
            raise HTTPException(status_code=429, detail=TOO_MANY_ATTEMPTS_MESSAGE)
        bucket.append(now)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


def _bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail=SESSION_INVALID_MESSAGE)
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise HTTPException(status_code=401, detail=SESSION_INVALID_MESSAGE)
    return credentials.strip()


def require_user(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency: the signed-in username, or 401."""
    token = _bearer(authorization)
    try:
        return read_token(token)
    except AuthError:
        raise HTTPException(status_code=401, detail=SESSION_INVALID_MESSAGE)


@router.post("/auth/register", status_code=201)
def register(
    body: RegisterRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    """Create a local account. The user signs in afterwards, separately."""
    client_host = request.client.host if request.client else "unknown"
    _record_register_attempt(client_host)

    username = body.username.strip().lower()
    if not USERNAME_PATTERN.match(username):
        raise HTTPException(status_code=422, detail=USERNAME_RULE)
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail=PASSWORD_RULE)

    taken = db.execute(select(AppUser.id).where(AppUser.username == username)).first()
    env_username = str(settings.axiom_username or "").strip().lower()
    if taken is not None or username == env_username:
        raise HTTPException(status_code=409, detail=USERNAME_TAKEN_MESSAGE)

    db.add(AppUser(username=username, password_hash=hash_password(body.password)))
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced for the same name; the unique index decided it.
        db.rollback()
        raise HTTPException(status_code=409, detail=USERNAME_TAKEN_MESSAGE)

    return {"username": username}


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """Exchange a local account's credentials for a token.

    A registered account is checked first, then the `.env` account, so the
    original single account still signs in. Every failure answers the same 401.
    """
    if not is_configured():
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_MESSAGE)

    username = body.username.strip().lower()
    account = db.execute(
        select(AppUser).where(AppUser.username == username)
    ).scalar_one_or_none()

    signed_in = None
    if account is not None and verify_password(body.password, account.password_hash):
        signed_in = account.username

    if signed_in is None:
        # The `.env` account is compared exactly as configured, so its case is
        # preserved; a registered name is always stored lowercase.
        username_ok = hmac.compare_digest(
            body.username.encode("utf-8"), str(settings.axiom_username).encode("utf-8")
        )
        password_ok = verify_password(body.password, settings.axiom_password_hash or "")
        if username_ok and password_ok:
            signed_in = body.username

    if signed_in is None:
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS_MESSAGE)

    try:
        token = issue_token(signed_in)
    except AuthError:
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_MESSAGE)

    return {
        "token": token,
        "username": signed_in,
        "expires_at": token_expiry().isoformat(),
    }


@router.get("/auth/me")
def me(username: str = Depends(require_user)) -> dict:
    """The signed-in username, for a token the frontend already holds."""
    return {"username": username}
