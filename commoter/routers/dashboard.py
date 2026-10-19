"""Home screen: the groups the signed-in user belongs to."""

from __future__ import annotations

from collections import Counter
from typing import NamedTuple

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import CarpoolGroup, Membership, User
from ..security import require_user
from ..templating import render

router = APIRouter()


class GroupCard(NamedTuple):
    """One row on the home screen: a series, shown at its latest month."""

    group: CarpoolGroup
    month_count: int


def _collapse_to_series(groups) -> list[GroupCard]:
    """One card per series. `groups` must already be month-desc.

    Collapsed in Python rather than SQL for the same reason the money is: the
    row count per user is small and the result stays exact and obvious.
    """
    counts = Counter(group.series_key for group in groups)
    latest: dict[tuple, CarpoolGroup] = {}
    for group in groups:
        latest.setdefault(group.series_key, group)
    # `setdefault` over a month-desc list keeps the newest month of each series,
    # and the dict keeps that insertion order, so the cards are already sorted.
    return [GroupCard(group, counts[group.series_key]) for group in latest.values()]


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
    return render(
        request, "dashboard/index.html", user=user, cards=_collapse_to_series(groups)
    )
