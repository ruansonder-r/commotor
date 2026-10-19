"""Test harness.

Every environment variable has to be in place before `commoter.config` is
imported, because the settings object is cached and the engine is built from it
at import time.
"""

from __future__ import annotations

import os
import re
import tempfile

_TMP = tempfile.mkdtemp(prefix="commoter-tests-")
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SESSION_SECRET"] = "test-secret-not-used-anywhere-real"
os.environ["FIREBASE_PROJECT_ID"] = "commoter-test"
os.environ["ADMIN_EMAILS"] = "boss@example.com"

import datetime as dt  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from commoter.db import Base, SessionLocal, engine  # noqa: E402
from commoter.main import app  # noqa: E402
from commoter.models import (  # noqa: E402
    Car,
    CarpoolGroup,
    CarpoolSeries,
    Membership,
    Trip,
    TripLog,
    User,
)
from commoter.security import get_current_user  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sign_in():
    """Stand in for a verified Firebase session."""

    def _sign_in(user: User) -> User:
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _sign_in


# --- Factories --------------------------------------------------------------


@pytest.fixture
def make():
    class Factory:
        def __init__(self) -> None:
            self.counter = 0

        def _next(self) -> int:
            self.counter += 1
            return self.counter

        def user(self, db, *, name="Alice Smith", email=None, admin=False) -> User:
            n = self._next()
            user = User(
                uid=f"uid-{n}",
                email=email or f"user{n}@example.com",
                display_name=name,
                is_admin=admin,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

        def series(self, db, *, name="Commute") -> CarpoolSeries:
            series = CarpoolSeries(name=name)
            db.add(series)
            db.commit()
            db.refresh(series)
            return series

        def group(
            self,
            db,
            *,
            cost_per_km="1.60",
            distance_km="70",
            name="Commute",
            month=dt.date(2026, 5, 1),
            series=None,
        ) -> CarpoolGroup:
            n = self._next()
            car = Car(name=f"V40 {n}", cost_per_km=Decimal(cost_per_km))
            trip = Trip(name=f"Commute {n}", distance_km=Decimal(distance_km))
            db.add_all([car, trip])
            db.flush()
            group = CarpoolGroup(
                name=name,
                month=month,
                car_id=car.id,
                trip_id=trip.id,
                series_id=series.id if series else None,
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            return group

        def membership(self, db, user, group, split="1.0") -> Membership:
            membership = Membership(
                user_id=user.id,
                carpool_group_id=group.id,
                cost_split_percentage=Decimal(split),
            )
            db.add(membership)
            db.commit()
            db.refresh(group)
            return membership

        def trip_log(self, db, group, user, count=1) -> TripLog:
            log = TripLog(
                carpool_group_id=group.id,
                recorded_by_user_id=user.id,
                occurred_at=dt.datetime.now(dt.UTC),
                trip_count=count,
            )
            db.add(log)
            db.commit()
            db.refresh(group)
            return log

    return Factory()


# --- Helpers ----------------------------------------------------------------


def csrf_token_from(client: TestClient, path: str = "/session/new") -> str:
    """Round-trip a real page so the session cookie and token actually match."""
    html = client.get(path).text
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert match, f"no csrf-token meta tag on {path}"
    return match.group(1)
