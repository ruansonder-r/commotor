"""Append-only trip log: one row per tap of + or -."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ValidationError
from ..models import TripLog, User
from ..security import require_user, verify_csrf
from ..templating import redirect, render_turbo_stream, wants_turbo_stream
from ..validation import assert_can_log_trip, assert_trip_count
from .carpool_groups import load_group_for_user

router = APIRouter(dependencies=[Depends(verify_csrf)])


async def _log(request: Request, db: Session, user: User, group_id: int, delta: int):
    group = load_group_for_user(db, user, group_id)

    try:
        assert_can_log_trip(group)
        assert_trip_count(delta)
        if delta < 0 and group.total_trips <= 0:
            raise ValidationError("Already at zero trips.")
    except ValidationError as exc:
        return redirect(
            request, f"/carpool_groups/{group.id}", alert=" ".join(exc.messages)
        )

    db.add(
        TripLog(
            carpool_group_id=group.id,
            recorded_by_user_id=user.id,
            occurred_at=dt.datetime.now(dt.UTC),
            trip_count=delta,
        )
    )
    db.commit()
    db.refresh(group)

    if wants_turbo_stream(request):
        return render_turbo_stream(
            request, "trip_logs/create.turbo_stream.html", user=user, group=group
        )
    return redirect(request, f"/carpool_groups/{group.id}")


@router.post("/carpool_groups/{group_id}/trip_logs")
async def create(
    group_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    return await _log(request, db, user, group_id, 1)


@router.post("/carpool_groups/{group_id}/trip_logs/decrement")
async def decrement(
    group_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    return await _log(request, db, user, group_id, -1)
