"""Firebase ID token verification and the session exchange."""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from commoter import security
from commoter.models import User
from commoter.routers import sessions as sessions_router

PROJECT = "commoter-test"
KID = "test-key-1"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def stub_google_certificates(monkeypatch):
    monkeypatch.setattr(
        security, "_fetch_certificates", lambda: {KID: _private_key.public_key()}
    )


def make_token(**overrides) -> str:
    now = dt.datetime.now(dt.UTC)
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": "firebase-uid-123",
        "iat": int(now.timestamp()) - 10,
        "exp": int((now + dt.timedelta(hours=1)).timestamp()),
        "email": "alice@example.com",
        "name": "Alice Smith",
    }
    claims.update(overrides)
    headers = {"kid": overrides.pop("_kid", KID)}
    return jwt.encode(claims, _private_key, algorithm="RS256", headers=headers)


def test_a_well_formed_token_verifies():
    claims = security.verify_firebase_token(make_token())
    assert claims["sub"] == "firebase-uid-123"
    assert claims["email"] == "alice@example.com"


def test_a_token_for_another_project_is_rejected():
    with pytest.raises(security.InvalidToken):
        security.verify_firebase_token(make_token(aud="someone-elses-project"))


def test_a_token_from_the_wrong_issuer_is_rejected():
    with pytest.raises(security.InvalidToken):
        security.verify_firebase_token(make_token(iss="https://evil.example.com"))


def test_an_expired_token_is_rejected():
    past = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
    with pytest.raises(security.InvalidToken):
        security.verify_firebase_token(
            make_token(exp=int(past.timestamp()), iat=int(past.timestamp()) - 10)
        )


def test_a_token_with_an_unknown_signing_key_is_rejected():
    token = jwt.encode(
        {
            "iss": f"https://securetoken.google.com/{PROJECT}",
            "aud": PROJECT,
            "sub": "x",
            "iat": 0,
            "exp": 9999999999,
        },
        _private_key,
        algorithm="RS256",
        headers={"kid": "not-a-real-kid"},
    )
    with pytest.raises(security.InvalidToken):
        security.verify_firebase_token(token)


def test_a_symmetrically_signed_token_is_rejected():
    """Guards the classic alg-confusion downgrade."""
    token = jwt.encode(
        {
            "iss": f"https://securetoken.google.com/{PROJECT}",
            "aud": PROJECT,
            "sub": "x",
            "iat": 0,
            "exp": 9999999999,
        },
        "shared-secret",
        algorithm="HS256",
        headers={"kid": KID},
    )
    with pytest.raises(security.InvalidToken):
        security.verify_firebase_token(token)


def test_a_token_without_a_subject_is_rejected():
    with pytest.raises(security.InvalidToken):
        security.verify_firebase_token(make_token(sub=""))


# --- POST /session ----------------------------------------------------------


def accept(monkeypatch, **claims):
    merged = {
        "sub": "firebase-uid-123",
        "email": "alice@example.com",
        "name": "Alice Smith",
    }
    merged.update(claims)
    monkeypatch.setattr(
        sessions_router, "verify_firebase_token", lambda _token: merged
    )


def test_signing_in_creates_the_user_and_the_session(client, db, monkeypatch):
    accept(monkeypatch)

    response = client.post("/session", json={"firebase_token": "anything"})
    assert response.status_code == 201

    user = db.scalar(select(User).where(User.uid == "firebase-uid-123"))
    assert user is not None
    assert user.display_name == "Alice Smith"
    assert user.is_admin is False

    # The cookie that came back is a real session.
    assert client.get("/dashboard").status_code == 200


def test_signing_in_again_updates_rather_than_duplicates(client, db, monkeypatch):
    accept(monkeypatch)
    client.post("/session", json={"firebase_token": "t"})
    accept(monkeypatch, name="Alice Renamed")
    client.post("/session", json={"firebase_token": "t"})

    users = db.scalars(select(User)).all()
    assert len(users) == 1
    db.refresh(users[0])
    assert users[0].display_name == "Alice Renamed"


def test_a_listed_email_is_granted_admin(client, db, monkeypatch):
    accept(monkeypatch, email="boss@example.com", sub="boss-uid")

    client.post("/session", json={"firebase_token": "t"})

    user = db.scalar(select(User).where(User.uid == "boss-uid"))
    assert user.is_admin is True


def test_a_name_less_account_falls_back_to_user(client, db, monkeypatch):
    accept(monkeypatch, name="")
    client.post("/session", json={"firebase_token": "t"})
    assert db.scalar(select(User)).display_name == "User"


def test_a_rejected_token_creates_nothing(client, db, monkeypatch):
    def reject(_token):
        raise security.InvalidToken("nope")

    monkeypatch.setattr(sessions_router, "verify_firebase_token", reject)

    response = client.post("/session", json={"firebase_token": "bad"})
    assert response.status_code == 401
    assert db.scalars(select(User)).all() == []


def test_signing_out_clears_the_session(client, db, monkeypatch):
    from .conftest import csrf_token_from

    accept(monkeypatch)
    client.post("/session", json={"firebase_token": "t"})
    token = csrf_token_from(client, "/dashboard")

    client.post("/session/sign_out", data={"_csrf": token}, follow_redirects=False)

    assert client.get("/", follow_redirects=False).status_code == 303


def test_removing_an_email_from_the_admin_list_demotes_on_next_sign_in(
    client, db, monkeypatch
):
    accept(monkeypatch, email="boss@example.com", sub="boss-uid")
    client.post("/session", json={"firebase_token": "t"})
    assert db.scalar(select(User).where(User.uid == "boss-uid")).is_admin is True

    from commoter.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_emails", {"someone-else@example.com"})
    client.post("/session", json={"firebase_token": "t"})

    user = db.scalar(select(User).where(User.uid == "boss-uid"))
    db.refresh(user)
    assert user.is_admin is False
