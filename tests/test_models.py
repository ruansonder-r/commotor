"""The cost arithmetic — the part that has to stay exactly right."""

from __future__ import annotations

from decimal import Decimal


def test_trip_cost_is_rate_times_distance(db, make):
    group = make.group(db, cost_per_km="1.60", distance_km="70")
    assert group.trip_cost == Decimal("112.0000")


def test_monthly_tally_multiplies_by_logged_trips(db, make):
    group = make.group(db, cost_per_km="2.50", distance_km="40")
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    for _ in range(10):
        make.trip_log(db, group, user)

    assert group.total_trips == 10
    assert group.monthly_tally == Decimal("1000.0000")


def test_amount_owed_splits_the_tally_by_percentage(db, make):
    group = make.group(db, cost_per_km="2.50", distance_km="40")
    alice = make.user(db, name="Alice")
    bob = make.user(db, name="Bob")
    carol = make.user(db, name="Carol")
    make.membership(db, alice, group, "0.30")
    make.membership(db, bob, group, "0.40")
    make.membership(db, carol, group, "0.30")
    for _ in range(10):
        make.trip_log(db, group, alice)

    owed = {m.user.display_name: m.amount_owed for m in group.memberships}
    assert owed["Alice"] == Decimal("300.0000")
    assert owed["Bob"] == Decimal("400.0000")
    assert owed["Carol"] == Decimal("300.0000")
    assert sum(owed.values()) == group.monthly_tally


def test_negative_logs_reduce_the_tally(db, make):
    group = make.group(db, cost_per_km="1.00", distance_km="10")
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    make.trip_log(db, group, user, count=1)
    make.trip_log(db, group, user, count=1)
    make.trip_log(db, group, user, count=-1)

    assert group.total_trips == 1
    assert group.monthly_tally == Decimal("10.0000")


def test_thirds_still_count_as_a_complete_split(db, make):
    """0.3333 x 3 = 0.9999 — inside the tolerance Rails used."""
    group = make.group(db)
    for _ in range(3):
        make.membership(db, make.user(db), group, "0.3333")

    assert group.splits_complete is True


def test_incomplete_split_is_detected(db, make):
    group = make.group(db)
    make.membership(db, make.user(db), group, "0.5")

    assert group.splits_complete is False


def test_history_is_newest_first_even_within_the_same_second(db, make):
    """SQLite timestamps round to the second; the id breaks the tie."""
    group = make.group(db)
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    logs = [make.trip_log(db, group, user, count=1) for _ in range(5)]

    db.refresh(group)
    assert [log.id for log in group.trip_logs] == sorted(
        (log.id for log in logs), reverse=True
    )
