"""Business rules, ported from the ActiveRecord validations.

Messages deliberately echo Rails' `errors.full_messages` so the existing form
templates read the same.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import ValidationError
from .models import ONE, ZERO, Car, CarpoolGroup, Membership, Trip, User

SPLIT_TOLERANCE = Decimal("0.001")


# --- Field parsing ----------------------------------------------------------


def parse_required_string(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{label} can't be blank")
    return text


def parse_positive_decimal(value: str | None, label: str) -> Decimal:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{label} can't be blank")
    try:
        number = Decimal(text)
    except InvalidOperation:
        raise ValidationError(f"{label} is not a number") from None
    if number <= ZERO:
        raise ValidationError(f"{label} must be greater than 0")
    return number


def parse_split(value: str | None, label: str = "Cost split percentage") -> Decimal:
    number = parse_positive_decimal(value, label)
    if number > ONE:
        raise ValidationError(f"{label} must be less than or equal to 1")
    return number


def parse_date(value: str | None, label: str) -> dt.date:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{label} can't be blank")
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise ValidationError(f"{label} is not a valid date") from None


def parse_fk(db: Session, model, value: str | None, label: str):
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{label} must exist")
    try:
        record = db.get(model, int(text))
    except ValueError:
        raise ValidationError(f"{label} must exist") from None
    if record is None:
        raise ValidationError(f"{label} must exist")
    return record


# --- Model-level rules ------------------------------------------------------


def validate_car_fields(form) -> dict:
    return {
        "name": parse_required_string(form.get("name"), "Name"),
        "cost_per_km": parse_positive_decimal(form.get("cost_per_km"), "Cost per km"),
    }


def validate_trip_fields(form) -> dict:
    return {
        "name": parse_required_string(form.get("name"), "Name"),
        "distance_km": parse_positive_decimal(form.get("distance_km"), "Distance km"),
    }


def validate_carpool_group_fields(db: Session, form) -> dict:
    return {
        "name": parse_required_string(form.get("name"), "Name"),
        "month": parse_date(form.get("month"), "Month"),
        "car_id": parse_fk(db, Car, form.get("car_id"), "Car").id,
        "trip_id": parse_fk(db, Trip, form.get("trip_id"), "Trip").id,
    }


def validate_membership_fields(
    db: Session, form, *, exclude_id: int | None = None
) -> dict:
    user = parse_fk(db, User, form.get("user_id"), "User")
    group = parse_fk(db, CarpoolGroup, form.get("carpool_group_id"), "Group")
    split = parse_split(form.get("cost_split_percentage"))

    duplicate = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.carpool_group_id == group.id,
            Membership.id != (exclude_id or -1),
        )
    )
    if duplicate is not None:
        raise ValidationError("User has already been taken")

    others = sum(
        (m.cost_split_percentage for m in group.memberships if m.id != exclude_id),
        ZERO,
    )
    if others + split > ONE + SPLIT_TOLERANCE:
        raise ValidationError(
            "Cost split percentage would cause group total to exceed 100%"
        )

    return {
        "user_id": user.id,
        "carpool_group_id": group.id,
        "cost_split_percentage": split,
    }


def assert_can_log_trip(group: CarpoolGroup) -> None:
    """A group needs members whose splits add to exactly 100% before logging."""
    if not group.memberships:
        raise ValidationError(
            "Cannot log a trip until the group has at least one member"
        )
    if not group.splits_complete:
        raise ValidationError(
            "Cannot log a trip until all membership splits sum to 100%"
        )


def assert_trip_count(value: int) -> int:
    if value == 0:
        raise ValidationError("Trip count must be other than 0")
    return value


def assert_removable(record: Car | Trip, label: str) -> None:
    """Mirrors `dependent: :restrict_with_error`."""
    if record.carpool_groups:
        raise ValidationError(
            f"Cannot remove this {label} because carpool groups still reference it"
        )
