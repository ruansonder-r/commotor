"""Sign-in: exchange a Firebase ID token for a signed session cookie."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import User
from ..security import InvalidToken, sign_in, sign_out, verify_csrf, verify_firebase_token
from ..templating import redirect, render

router = APIRouter()


@router.get("/session/new")
async def new(request: Request):
    return render(request, "sessions/new.html")


@router.post("/session")
async def create(request: Request, db: Session = Depends(get_db)):
    """No CSRF check here on purpose: the Firebase ID token is itself a signed
    assertion of identity, so a forged cross-site post proves nothing without one.
    """
    payload = await request.json() if _is_json(request) else dict(await request.form())
    token = (payload.get("firebase_token") or "").strip()
    if not token:
        return JSONResponse({"error": "Missing firebase_token"}, status_code=401)

    try:
        claims = verify_firebase_token(token)
    except InvalidToken as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)
    except Exception as exc:  # network failure reaching Google's cert endpoint
        return JSONResponse(
            {"error": f"Could not verify token: {exc}"}, status_code=503
        )

    email = (claims.get("email") or "").strip()
    if not email:
        return JSONResponse({"error": "Token carries no email address"}, status_code=401)

    settings = get_settings()
    user = db.scalar(select(User).where(User.uid == claims["sub"]))
    if user is None:
        # Fall back to email so a re-created Firebase account reuses the record.
        user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(uid=claims["sub"])
        db.add(user)

    user.uid = claims["sub"]
    user.email = email
    user.display_name = (claims.get("name") or "").strip() or "User"
    # ADMIN_EMAILS is authoritative whenever it is configured, so dropping
    # someone from the list actually demotes them on their next sign-in rather
    # than leaving a stale admin flag behind. An empty list changes nothing.
    if settings.admin_emails:
        user.is_admin = email.lower() in settings.admin_emails

    db.commit()
    db.refresh(user)

    sign_in(request, user)
    return JSONResponse({"status": "ok"}, status_code=201)


@router.post("/session/sign_out", dependencies=[Depends(verify_csrf)])
async def destroy(request: Request):
    sign_out(request)
    return redirect(request, "/session/new")


def _is_json(request: Request) -> bool:
    return request.headers.get("content-type", "").startswith("application/json")
