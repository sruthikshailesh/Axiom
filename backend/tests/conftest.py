from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit, urlunsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Point the app at a separate test database before importing it.
BASE_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://axiom:axiom@localhost:5432/axiom"
)


def _derive_test_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    return urlunsplit(parts._replace(path=parts.path.rstrip("/") + "_test"))


TEST_DATABASE_URL = os.environ.get("DATABASE_URL_TEST") or _derive_test_url(
    BASE_DATABASE_URL
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def _ensure_database(url: str) -> None:
    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    admin_url = urlunsplit(parts._replace(path="/postgres", query=""))
    admin_url = admin_url.replace("postgresql+psycopg://", "postgresql://", 1)

    with psycopg.connect(admin_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
        if not exists:
            connection.execute('CREATE DATABASE "{}"'.format(name))


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    """Create the test database if needed, migrate it, and start clean."""
    _ensure_database(TEST_DATABASE_URL)

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE chunk, source, run, claim, evidence, conflict, "
                "supersession, app_user RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()

    yield


@pytest.fixture()
def db() -> Iterator[Session]:
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@dataclass(frozen=True)
class TestAccount:
    """Credentials generated for this test run; nothing is committed."""

    username: str
    password: str
    token: str


@pytest.fixture(scope="session", autouse=True)
def auth_env() -> Iterator[TestAccount]:
    """Configure the single local account with values made up per session."""
    from app.auth import hash_password, issue_token
    from app.config import settings

    previous = (
        settings.axiom_username,
        settings.axiom_password_hash,
        settings.axiom_secret,
        settings.axiom_token_hours,
    )

    account = TestAccount(
        username="user-{}".format(secrets.token_hex(4)),
        password=secrets.token_urlsafe(18),
        token="",
    )

    settings.axiom_username = account.username
    settings.axiom_password_hash = hash_password(account.password)
    settings.axiom_secret = secrets.token_hex(32)
    settings.axiom_token_hours = 12

    account = TestAccount(
        username=account.username, password=account.password, token=issue_token(account.username)
    )

    try:
        yield account
    finally:
        (
            settings.axiom_username,
            settings.axiom_password_hash,
            settings.axiom_secret,
            settings.axiom_token_hours,
        ) = previous


@pytest.fixture()
def auth_header(auth_env: TestAccount) -> dict:
    return {"Authorization": "Bearer {}".format(auth_env.token)}


@pytest.fixture()
def client(auth_env: TestAccount, auth_header: dict) -> Iterator[TestClient]:
    """A signed-in client: every request carries a valid test token."""
    from app.main import app

    with TestClient(app) as test_client:
        test_client.headers.update(auth_header)
        yield test_client


@pytest.fixture()
def anon_client() -> Iterator[TestClient]:
    """A client with no credentials, for the auth tests."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
