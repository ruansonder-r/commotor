"""Home screen: the groups the signed-in user belongs to."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import CarpoolGroup, Membership, User
from ..security import require_user
from ..templating import render

router = APIRouter()


@router.get("/")
@router.get("/dashboard")
async def index(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    groups = (
        db.scalars(
            select(CarpoolGroup)
            .join(Membership)
            .where(Membership.user_id == user.id)
            .options(selectinload(CarpoolGroup.trip_logs))
            .order_by(CarpoolGroup.month.desc())
        )
        .unique()
        .all()
    )
    return render(request, "dashboard/index.html", user=user, groups=groups)
