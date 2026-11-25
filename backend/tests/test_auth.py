from __future__ import annotations

import hashlib
import hmac
import json
import time

from app.auth import NOT_CONFIGURED_MESSAGE, _b64encode, hash_password, verify_password
from app.config import settings
from app.routes.auth import BAD_CREDENTIALS_MESSAGE, SESSION_INVALID_MESSAGE


def _sign(payload: dict, secret: str) -> str:
    """Build a token with an arbitrary payload, signed with the test secret."""
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(
        hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return "{}.{}".format(encoded, signature)


def test_password_hash_round_trips() -> None:
    stored = hash_password("correct horse battery staple")
    assert stored.startswith("pbkdf2_sha256$200000$")
    assert verify_password("correct horse battery staple", stored)
    assert not verify_password("correct horse battery stapler", stored)
    assert not verify_password("correct horse battery staple", "not-a-hash")
    assert not verify_password("correct horse battery staple", "")


def test_hash_is_salted_so_two_hashes_differ() -> None:
    assert hash_password("same password") != hash_password("same password")


def test_login_succeeds_with_the_right_password(anon_client, auth_env) -> None:
    response = anon_client.post(
        "/auth/login",
        json={"username": auth_env.username, "password": auth_env.password},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == auth_env.username
    assert body["token"].count(".") == 1
    assert body["expires_at"]

    me = anon_client.get(
        "/auth/me", headers={"Authorization": "Bearer {}".format(body["token"])}
    )
    assert me.status_code == 200
    assert me.json() == {"username": auth_env.username}


def test_wrong_password_and_wrong_username_are_indistinguishable(
    anon_client, auth_env
) -> None:
    wrong_password = anon_client.post(
        "/auth/login",
        json={"username": auth_env.username, "password": auth_env.password + "x"},
    )
    wrong_username = anon_client.post(
        "/auth/login",
        json={"username": auth_env.username + "x", "password": auth_env.password},
    )

    assert wrong_password.status_code == 401
    assert wrong_username.status_code == 401
    assert wrong_password.json() == {"detail": BAD_CREDENTIALS_MESSAGE}
    assert wrong_username.json() == wrong_password.json()
    assert BAD_CREDENTIALS_MESSAGE == "Incorrect username or password."


def test_login_answers_503_when_sign_in_is_not_configured(
    anon_client, auth_env, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "axiom_secret", None)

    response = anon_client.post(
        "/auth/login",
        json={"username": auth_env.username, "password": auth_env.password},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": NOT_CONFIGURED_MESSAGE}


def test_protected_routes_require_a_token(anon_client) -> None:
    for path in ("/sources", "/search?q=ionosphere", "/runs/1", "/dashboard/summary"):
        response = anon_client.get(path)
        assert response.status_code == 401, path
        assert response.json() == {"detail": SESSION_INVALID_MESSAGE}

    assert anon_client.post("/runs", json={"question": "anything"}).status_code == 401
    assert anon_client.post("/demo/run").status_code == 401


def test_health_and_sign_in_stay_public(anon_client) -> None:
    assert anon_client.get("/health").status_code == 200


def test_forged_token_is_rejected(anon_client) -> None:
    forged = _sign({"sub": "someone", "exp": int(time.time()) + 600}, "not-the-secret")

    response = anon_client.get(
        "/sources", headers={"Authorization": "Bearer {}".format(forged)}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": SESSION_INVALID_MESSAGE}


def test_tampered_signature_is_rejected(anon_client, auth_env) -> None:
    payload, signature = auth_env.token.split(".")
    flipped = signature[:-1] + ("A" if signature[-1] != "A" else "B")

    response = anon_client.get(
        "/sources", headers={"Authorization": "Bearer {}.{}".format(payload, flipped)}
    )

    assert response.status_code == 401


def test_expired_token_is_rejected(anon_client, auth_env) -> None:
    expired = _sign(
        {"sub": auth_env.username, "exp": int(time.time()) - 60}, settings.axiom_secret
    )

    response = anon_client.get(
        "/sources", headers={"Authorization": "Bearer {}".format(expired)}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": SESSION_INVALID_MESSAGE}


def test_malformed_authorization_header_is_rejected(anon_client) -> None:
    for header in ("Bearer", "Bearer ", "Basic abc", "nonsense", auth_env_token_placeholder()):
        response = anon_client.get("/sources", headers={"Authorization": header})
        assert response.status_code == 401, header


def auth_env_token_placeholder() -> str:
    """A structurally valid header with a token that is not signed at all."""
    return "Bearer not-a-real-token"
