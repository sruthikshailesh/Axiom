from __future__ import annotations

import secrets

import pytest

from app.auth import verify_password
from app.models import AppUser
from app.routes.auth import (
    BAD_CREDENTIALS_MESSAGE,
    PASSWORD_RULE,
    TOO_MANY_ATTEMPTS_MESSAGE,
    USERNAME_RULE,
    USERNAME_TAKEN_MESSAGE,
    reset_register_limits,
)


@pytest.fixture(autouse=True)
def fresh_limits():
    """The limiter lives in memory, so every test starts with an empty window."""
    reset_register_limits()
    yield
    reset_register_limits()


@pytest.fixture()
def new_account() -> dict:
    """A username and password made up for this test; nothing is committed."""
    return {
        "username": "reader.{}".format(secrets.token_hex(4)),
        "password": secrets.token_urlsafe(12),
    }


def test_register_creates_an_account_with_a_hash_only(anon_client, db, new_account) -> None:
    response = anon_client.post("/auth/register", json=new_account)

    assert response.status_code == 201, response.text
    assert response.json() == {"username": new_account["username"]}

    stored = (
        db.query(AppUser).filter(AppUser.username == new_account["username"]).one_or_none()
    )
    assert stored is not None
    assert stored.password_hash != new_account["password"]
    assert stored.password_hash.startswith("pbkdf2_sha256$")
    assert verify_password(new_account["password"], stored.password_hash)
    assert stored.created_at is not None


def test_register_lowercases_the_username(anon_client, new_account) -> None:
    upper = new_account["username"].upper()

    response = anon_client.post(
        "/auth/register", json={"username": upper, "password": new_account["password"]}
    )

    assert response.status_code == 201, response.text
    assert response.json() == {"username": upper.lower()}


def test_duplicate_username_answers_409(anon_client, new_account) -> None:
    first = anon_client.post("/auth/register", json=new_account)
    assert first.status_code == 201

    again = anon_client.post("/auth/register", json=new_account)
    differing_case = anon_client.post(
        "/auth/register",
        json={
            "username": new_account["username"].upper(),
            "password": new_account["password"],
        },
    )

    for response in (again, differing_case):
        assert response.status_code == 409
        assert response.json() == {"detail": USERNAME_TAKEN_MESSAGE}
    assert USERNAME_TAKEN_MESSAGE == "That username is already taken."


def test_short_password_answers_422_with_the_rule(anon_client, new_account) -> None:
    response = anon_client.post(
        "/auth/register",
        json={"username": new_account["username"], "password": "short"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": PASSWORD_RULE}


def test_bad_username_answers_422_with_the_rule(anon_client, new_account) -> None:
    for username in ("ab", "a" * 33, "has space", "semi;colon"):
        response = anon_client.post(
            "/auth/register", json={"username": username, "password": new_account["password"]}
        )
        assert response.status_code == 422, username
        assert response.json() == {"detail": USERNAME_RULE}


def test_registered_user_can_sign_in(anon_client, new_account) -> None:
    assert anon_client.post("/auth/register", json=new_account).status_code == 201

    response = anon_client.post("/auth/login", json=new_account)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == new_account["username"]
    assert body["token"].count(".") == 1

    me = anon_client.get(
        "/auth/me", headers={"Authorization": "Bearer {}".format(body["token"])}
    )
    assert me.status_code == 200
    assert me.json() == {"username": new_account["username"]}


def test_registered_user_signs_in_with_any_username_case(anon_client, new_account) -> None:
    assert anon_client.post("/auth/register", json=new_account).status_code == 201

    response = anon_client.post(
        "/auth/login",
        json={
            "username": new_account["username"].upper(),
            "password": new_account["password"],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["username"] == new_account["username"]


def test_env_account_still_signs_in(anon_client, auth_env) -> None:
    response = anon_client.post(
        "/auth/login",
        json={"username": auth_env.username, "password": auth_env.password},
    )

    assert response.status_code == 200, response.text
    assert response.json()["username"] == auth_env.username


def test_wrong_password_for_a_registered_user_is_generic(anon_client, new_account) -> None:
    assert anon_client.post("/auth/register", json=new_account).status_code == 201

    wrong_password = anon_client.post(
        "/auth/login",
        json={"username": new_account["username"], "password": new_account["password"] + "x"},
    )
    unknown_user = anon_client.post(
        "/auth/login",
        json={"username": "nobody.{}".format(secrets.token_hex(4)), "password": "whatever1"},
    )

    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json() == {"detail": BAD_CREDENTIALS_MESSAGE}
    assert unknown_user.json() == wrong_password.json()
    assert BAD_CREDENTIALS_MESSAGE == "Incorrect username or password."


def test_register_is_rate_limited_per_address(anon_client, new_account) -> None:
    payload = {"username": new_account["username"], "password": "short"}

    for _ in range(10):
        assert anon_client.post("/auth/register", json=payload).status_code == 422

    blocked = anon_client.post("/auth/register", json=new_account)

    assert blocked.status_code == 429
    assert blocked.json() == {"detail": TOO_MANY_ATTEMPTS_MESSAGE}
