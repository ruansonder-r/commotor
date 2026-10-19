"""Business rules ported from the ActiveRecord validations."""

from __future__ import annotations

from decimal import Decimal

import pytest

from commoter.errors import ValidationError
from commoter.validation import (
    assert_can_log_trip,
    assert_removable,
    assert_trip_count,
    validate_car_fields,
    validate_carpool_group_fields,
    validate_membership_fields,
    validate_trip_fields,
)


@pytest.mark.parametrize(
    "value,message",
    [
        ("", "Cost per km can't be blank"),
        ("abc", "Cost per km is not a number"),
        ("0", "Cost per km must be greater than 0"),
        ("-1.5", "Cost per km must be greater than 0"),
    ],
)
def test_car_rate_must_be_a_positive_number(value, message):
    with pytest.raises(ValidationError) as exc:
        validate_car_fields({"name": "V40", "cost_per_km": value})
    assert message in exc.value.messages


def test_car_name_is_required():
    with pytest.raises(ValidationError) as exc:
        validate_car_fields({"name": "   ", "cost_per_km": "1.60"})
    assert "Name can't be blank" in exc.value.messages


def test_valid_car_parses_to_a_decimal():
    parsed = validate_car_fields({"name": " V40 ", "cost_per_km": "1.60"})
    assert parsed == {"name": "V40", "cost_per_km": Decimal("1.60")}


def test_trip_distance_must_be_positive():
    with pytest.raises(ValidationError):
        validate_trip_fields({"name": "Commute", "distance_km": "0"})


def test_group_requires_an_existing_car_and_trip(db, make):
    group = make.group(db)
    with pytest.raises(ValidationError) as exc:
        validate_carpool_group_fields(
            db,
            {
                "name": "Crew",
                "month": "2026-05-01",
                "car_id": "99999",
                "trip_id": str(group.trip_id),
            },
        )
    assert "Car must exist" in exc.value.messages


def test_group_month_must_parse(db, make):
    group = make.group(db)
    with pytest.raises(ValidationError) as exc:
        validate_carpool_group_fields(
            db,
            {
                "name": "Crew",
                "month": "not-a-date",
                "car_id": str(group.car_id),
                "trip_id": str(group.trip_id),
            },
        )
    assert "Month is not a valid date" in exc.value.messages


def test_split_above_one_is_rejected(db, make):
    group = make.group(db)
    user = make.user(db)
    with pytest.raises(ValidationError) as exc:
        validate_membership_fields(
            db,
            {
                "user_id": str(user.id),
                "carpool_group_id": str(group.id),
                "cost_split_percentage": "1.5",
            },
        )
    assert "Cost split percentage must be less than or equal to 1" in exc.value.messages


def test_splits_may_not_push_the_group_over_one_hundred_percent(db, make):
    group = make.group(db)
    make.membership(db, make.user(db), group, "0.70")
    newcomer = make.user(db)

    with pytest.raises(ValidationError) as exc:
        validate_membership_fields(
            db,
            {
                "user_id": str(newcomer.id),
                "carpool_group_id": str(group.id),
                "cost_split_percentage": "0.40",
            },
        )
    assert (
        "Cost split percentage would cause group total to exceed 100%"
        in exc.value.messages
    )


def test_splits_adding_to_exactly_one_hundred_percent_are_allowed(db, make):
    group = make.group(db)
    make.membership(db, make.user(db), group, "0.70")
    newcomer = make.user(db)

    parsed = validate_membership_fields(
        db,
        {
            "user_id": str(newcomer.id),
            "carpool_group_id": str(group.id),
            "cost_split_percentage": "0.30",
        },
    )
    assert parsed["cost_split_percentage"] == Decimal("0.30")


def test_a_user_can_only_join_a_group_once(db, make):
    group = make.group(db)
    user = make.user(db)
    make.membership(db, user, group, "0.50")

    with pytest.raises(ValidationError) as exc:
        validate_membership_fields(
            db,
            {
                "user_id": str(user.id),
                "carpool_group_id": str(group.id),
                "cost_split_percentage": "0.20",
            },
        )
    assert "User has already been taken" in exc.value.messages


def test_editing_a_membership_does_not_collide_with_itself(db, make):
    group = make.group(db)
    user = make.user(db)
    membership = make.membership(db, user, group, "0.50")

    parsed = validate_membership_fields(
        db,
        {
            "user_id": str(user.id),
            "carpool_group_id": str(group.id),
            "cost_split_percentage": "0.90",
        },
        exclude_id=membership.id,
    )
    assert parsed["cost_split_percentage"] == Decimal("0.90")


def test_logging_requires_at_least_one_member(db, make):
    group = make.group(db)
    with pytest.raises(ValidationError) as exc:
        assert_can_log_trip(group)
    assert "at least one member" in exc.value.messages[0]


def test_logging_requires_splits_to_total_one_hundred(db, make):
    group = make.group(db)
    make.membership(db, make.user(db), group, "0.60")
    with pytest.raises(ValidationError) as exc:
        assert_can_log_trip(group)
    assert "sum to 100%" in exc.value.messages[0]


def test_logging_is_allowed_once_splits_are_complete(db, make):
    group = make.group(db)
    make.membership(db, make.user(db), group, "1.0")
    assert_can_log_trip(group)  # does not raise


def test_a_zero_trip_count_is_meaningless():
    with pytest.raises(ValidationError):
        assert_trip_count(0)
    assert assert_trip_count(-1) == -1


def test_a_car_in_use_cannot_be_removed(db, make):
    group = make.group(db)
    with pytest.raises(ValidationError) as exc:
        assert_removable(group.car, "car")
    assert "carpool groups still reference it" in exc.value.messages[0]
