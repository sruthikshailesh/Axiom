from __future__ import annotations

import os
import sys
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
                "supersession RESTART IDENTITY CASCADE"
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


@pytest.fixture()
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
