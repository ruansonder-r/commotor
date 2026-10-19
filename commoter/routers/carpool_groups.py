"""Group detail: tally, member breakdown, and the +/- controls.

Also the only non-admin create route in the app — a member starting a group, or
rolling an existing one forward into the next month. Cars and trips stay admin
masterdata; a member picks from what is already there.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import NotFoundError, ValidationError
from ..models import ONE, Car, CarpoolGroup, CarpoolSeries, Membership, Trip, User
from ..security import require_user, verify_csrf
from ..templating import redirect, render
from ..validation import assert_month_is_free, validate_new_group_fields

router = APIRouter()


def load_group_for_user(db: Session, user: User, group_id: int) -> CarpoolGroup:
    """Scope every lookup through membership — a user may only see their groups."""
    group = db.get(CarpoolGroup, group_id)
    if group is None or not any(m.user_id == user.id for m in group.memberships):
        raise NotFoundError(f"No carpool group {group_id} for this user")
    return group


def groups_for_user(db: Session, user: User) -> list[CarpoolGroup]:
    """Every month the user belongs to, newest first."""
    return list(
        db.scalars(
            select(CarpoolGroup)
            .join(Membership)
            .where(Membership.user_id == user.id)
            .order_by(CarpoolGroup.month.desc())
        ).unique()
    )


def sibling_months_for_user(
    db: Session, user: User, group: CarpoolGroup
) -> list[CarpoolGroup]:
    """The months of this group's series that the user is actually in, newest first.

    Filtered by membership, not just by series: a user may be in June but not in
    May of the same series, and the switcher must not offer a month that would
    then 404.
    """
    if group.series_id is None:
        return [group]
    return list(
        db.scalars(
            select(CarpoolGroup)
            .join(Membership)
            .where(
                Membership.user_id == user.id,
                CarpoolGroup.series_id == group.series_id,
            )
            .order_by(CarpoolGroup.month.desc())
        ).unique()
    )


# --- Creating a month -------------------------------------------------------


def _next_month(month: dt.date) -> dt.date:
    """The 1st of the month after `month`. 32 days always clears a month."""
    return (month.replace(day=1) + dt.timedelta(days=32)).replace(day=1)


def _default_month(groups: list[CarpoolGroup]) -> str:
    """Prefill: the month after the user's newest, else this one. `YYYY-MM`."""
    latest = max((group.month for group in groups), default=None)
    # UTC like every other "now" in the app; on Vercel they are the same anyway.
    this_month = dt.datetime.now(dt.UTC).date().replace(day=1)
    month = _next_month(latest) if latest else this_month
    return month.strftime("%Y-%m")


def _as_int(value: str) -> int:
    """A hand-edited `copy_from` is an unknown group — a 404, not a 500."""
    try:
        return int(value)
    except ValueError:
        raise NotFoundError(f"No carpool group {value!r} for this user") from None


def _assert_month_free(
    db: Session, source: CarpoolGroup | None, month: dt.date
) -> None:
    if source is None:
        return  # a brand new series has no months to collide with
    if source.series_id is not None:
        assert_month_is_free(db, source.series_id, month)
    elif month == source.month:
        # The source has no series yet, so it is about to become the series'
        # only other month — and the only month already taken.
        raise ValidationError("Month has already been taken for this group")


def _series_for(
    db: Session, source: CarpoolGroup | None, name: str
) -> CarpoolSeries:
    if source is not None and source.series is not None:
        return source.series
    series = CarpoolSeries(name=name)
    db.add(series)
    db.flush()
    if source is not None:
        # Rolling forward a group that predates series threads the source onto
        # the new series too, so the history reads as one group, not two.
        source.series_id = series.id
    return series


def _copy_memberships(
    db: Session, source: CarpoolGroup | None, group: CarpoolGroup, user: User
) -> None:
    """Carry the source's members and splits over verbatim.

    An incomplete source stays incomplete: `assert_can_log_trip` already blocks
    logging, and rounding the splits up here would be inventing who owes what.
    """
    if source is None:
        db.add(
            Membership(
                user_id=user.id,
                carpool_group_id=group.id,
                cost_split_percentage=ONE,
            )
        )
        return
    for membership in source.memberships:
        db.add(
            Membership(
                user_id=membership.user_id,
                carpool_group_id=group.id,
                cost_split_percentage=membership.cost_split_percentage,
            )
        )


def _form_context(db: Session, user: User) -> dict:
    return {
        "cars": list(db.scalars(select(Car).order_by(Car.name))),
        "trips": list(db.scalars(select(Trip).order_by(Trip.name))),
        "my_groups": groups_for_user(db, user),
    }


# `/new` has to be registered before `/{group_id}`, or FastAPI matches "new"
# against the int path parameter and 422s instead of reaching this route.
@router.get("/carpool_groups/new")
async def new(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    context = _form_context(db, user)
    return render(
        request,
        "carpool_groups/new.html",
        user=user,
        values={"month": _default_month(context["my_groups"])},
        errors=[],
        **context,
    )


@router.post("/carpool_groups", dependencies=[Depends(verify_csrf)])
async def create(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    source = None
    copy_from = (form.get("copy_from") or "").strip()
    if copy_from:
        source = load_group_for_user(db, user, _as_int(copy_from))

    try:
        attributes = validate_new_group_fields(db, form)
        _assert_month_free(db, source, attributes["month"])
    except ValidationError as exc:
        # Nothing has been written yet — the series is only created below — so
        # `get_db`'s close() rolls the request back to exactly where it started.
        return render(
            request,
            "carpool_groups/new.html",
            user=user,
            status_code=422,
            values=dict(form),
            errors=exc.messages,
            **_form_context(db, user),
        )

    series = _series_for(db, source, attributes["name"])
    group = CarpoolGroup(**attributes, series_id=series.id)
    db.add(group)
    db.flush()
    _copy_memberships(db, source, group, user)
    db.commit()
    return redirect(
        request, f"/carpool_groups/{group.id}", notice="Carpool group created."
    )


@router.get("/carpool_groups/{group_id}")
async def show(
    group_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    group = load_group_for_user(db, user, group_id)
    return render(
        request,
        "carpool_groups/show.html",
        user=user,
        group=group,
        months=sibling_months_for_user(db, user, group),
    )
