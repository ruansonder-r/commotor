"""Firebase ID-token verification, session auth, and CSRF.

The Rails app leaned on the `firebase_id_token` gem plus Redis purely to cache
Google's signing certificates. Verification is a dozen lines of standard JWT
work, so this does it directly and caches the certificates in module scope —
which survives warm Vercel invocations and needs no Redis at all.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import secrets
import time
from typing import Any

import httpx
import jwt
from cryptography.x509 import load_pem_x509_certificate
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .errors import RedirectError
from .models import User

CERT_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
_cert_cache: dict[str, Any] = {"keys": {}, "expires_at": 0.0}


class InvalidToken(Exception):
    pass


def _fetch_certificates() -> dict[str, Any]:
    """Google's x509 signing certs, cached until their Cache-Control expires."""
    now = time.time()
    if _cert_cache["keys"] and now < _cert_cache["expires_at"]:
        return _cert_cache["keys"]

    response = httpx.get(CERT_URL, timeout=10.0)
    response.raise_for_status()

    max_age = 3600
    cache_control = response.headers.get("cache-control", "")
    for part in cache_control.split(","):
        part = part.strip()
        if part.startswith("max-age="):
            with contextlib.suppress(ValueError):
                max_age = int(part.removeprefix("max-age="))

    keys = {
        kid: load_pem_x509_certificate(pem.encode()).public_key()
        for kid, pem in response.json().items()
    }
    _cert_cache["keys"] = keys
    _cert_cache["expires_at"] = now + max_age
    return keys


def verify_firebase_token(token: str) -> dict[str, Any]:
    """Validate a Firebase ID token and return its claims.

    Raises InvalidToken for anything that does not check out.
    """
    settings = get_settings()
    project_id = settings.firebase_project_id
    if not project_id:
        raise InvalidToken("FIREBASE_PROJECT_ID is not configured")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidToken(f"Malformed token: {exc}") from exc

    if header.get("alg") != "RS256":
        raise InvalidToken("Token must be signed with RS256")

    kid = header.get("kid")
    keys = _fetch_certificates()
    if kid not in keys:
        # A rotation may have landed since we last cached; force one refresh.
        _cert_cache["expires_at"] = 0.0
        keys = _fetch_certificates()
    if kid not in keys:
        raise InvalidToken("Token signing key is not recognised")

    try:
        claims = jwt.decode(
            token,
            key=keys[kid],
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc

    if not claims.get("sub"):
        raise InvalidToken("Token has no subject")
    if claims.get("auth_time", 0) > dt.datetime.now(dt.UTC).timestamp() + 60:
        raise InvalidToken("Token auth_time is in the future")

    return claims


# --- Session auth -----------------------------------------------------------


def sign_in(request: Request, user: User) -> None:
    request.session["user_id"] = user.id


def sign_out(request: Request) -> None:
    request.session.pop("user_id", None)


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None:
        # Stale cookie pointing at a deleted user.
        request.session.pop("user_id", None)
    return user


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise RedirectError("/session/new")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise RedirectError("/dashboard", alert="Admins only.")
    return user


# --- CSRF -------------------------------------------------------------------

CSRF_FIELD = "_csrf"
CSRF_SESSION_KEY = "_csrf_token"


def csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


async def verify_csrf(request: Request) -> None:
    """FastAPI dependency guarding every state-changing form post."""
    expected = request.session.get(CSRF_SESSION_KEY)
    form = await request.form()
    supplied = form.get(CSRF_FIELD) or request.headers.get("x-csrf-token", "")
    if not expected or not secrets.compare_digest(str(supplied), str(expected)):
        raise RedirectError("/", alert="Your session expired. Please try again.")
