from __future__ import annotations

import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.auth import (
    NOT_CONFIGURED_MESSAGE,
    AuthError,
    is_configured,
    issue_token,
    read_token,
    token_expiry,
    verify_password,
)
from app.config import settings

router = APIRouter(tags=["auth"])

# One message for every rejected sign-in: the response must not reveal whether
# the username or the password was the wrong part.
BAD_CREDENTIALS_MESSAGE = "Incorrect username or password."
SESSION_INVALID_MESSAGE = "Your session has ended. Sign in again."


class LoginRequest(BaseModel):
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


@router.post("/auth/login")
def login(body: LoginRequest) -> dict:
    """Exchange the single local account's credentials for a token."""
    if not is_configured():
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_MESSAGE)

    username_ok = hmac.compare_digest(
        body.username.encode("utf-8"), str(settings.axiom_username).encode("utf-8")
    )
    password_ok = verify_password(body.password, settings.axiom_password_hash or "")

    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS_MESSAGE)

    try:
        token = issue_token(body.username)
    except AuthError:
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_MESSAGE)

    return {
        "token": token,
        "username": body.username,
        "expires_at": token_expiry().isoformat(),
    }


@router.get("/auth/me")
def me(username: str = Depends(require_user)) -> dict:
    """The signed-in username, for a token the frontend already holds."""
    return {"username": username}
