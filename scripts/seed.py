"""Idempotent seed data — the port of db/seeds.rb.

    python -m scripts.seed
"""

from __future__ import annotations

import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from commoter.db import SessionLocal  # noqa: E402
from commoter.models import Car, CarpoolGroup, Trip  # noqa: E402
from commoter.templating import money  # noqa: E402


def find_or_create(db, model, defaults: dict, **lookup):
    record = db.scalar(select(model).filter_by(**lookup))
    if record is None:
        record = model(**lookup, **defaults)
        db.add(record)
        db.flush()
    return record


def main() -> None:
    with SessionLocal() as db:
        car = find_or_create(db, Car, {"cost_per_km": Decimal("1.60")}, name="V40 1.6")
        trip = find_or_create(db, Trip, {"distance_km": Decimal("70")}, name="Commute")
        group = find_or_create(
            db,
            CarpoolGroup,
            {"car_id": car.id, "trip_id": trip.id},
            name="Commute",
            month=dt.date(2026, 5, 1),
        )
        db.commit()
        db.refresh(group)

        print("Seeded: 1 car, 1 trip, 1 group")
        print(f"  Trip cost per leg: R{money(group.trip_cost)}")
        print("  Add members via /admin/memberships — splits must total 100%")


if __name__ == "__main__":
    main()
