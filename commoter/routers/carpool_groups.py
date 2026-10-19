"""Group detail: tally, member breakdown, and the +/- controls."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import NotFoundError
from ..models import CarpoolGroup, User
from ..security import require_user
from ..templating import render

router = APIRouter()


def load_group_for_user(db: Session, user: User, group_id: int) -> CarpoolGroup:
    """Scope every lookup through membership — a user may only see their groups."""
    group = db.get(CarpoolGroup, group_id)
    if group is None or not any(m.user_id == user.id for m in group.memberships):
        raise NotFoundError(f"No carpool group {group_id} for this user")
    return group


@router.get("/carpool_groups/{group_id}")
async def show(
    group_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    group = load_group_for_user(db, user, group_id)
    return render(request, "carpool_groups/show.html", user=user, group=group)
