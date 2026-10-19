"""SQLAlchemy models — a direct port of the ActiveRecord models.

The derived money values (`trip_cost`, `monthly_tally`, `amount_owed`) are
computed in Python from loaded relationships rather than via SQL aggregates, so
they stay exact `Decimal` arithmetic end to end.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, Money

ZERO = Decimal("0")
ONE = Decimal("1")
# Rails compared split totals with a 0.001 tolerance; keep the same slack so a
# 1/3 + 1/3 + 1/3 group still counts as complete.
SPLIT_TOLERANCE = Decimal("0.001")


class TimestampMixin:
    # The Python-side default carries microseconds; the server default is only
    # a fallback, and on SQLite it would round to the second.
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        server_default=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    recorded_trip_logs: Mapped[list[TripLog]] = relationship(
        back_populates="recorded_by", foreign_keys="TripLog.recorded_by_user_id"
    )

    @property
    def carpool_groups(self) -> list[CarpoolGroup]:
        return [m.carpool_group for m in self.memberships]


class Car(TimestampMixin, Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_per_km: Mapped[Decimal] = mapped_column(Money(), nullable=False)

    carpool_groups: Mapped[list[CarpoolGroup]] = relationship(back_populates="car")


class Trip(TimestampMixin, Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    distance_km: Mapped[Decimal] = mapped_column(Money(), nullable=False)

    carpool_groups: Mapped[list[CarpoolGroup]] = relationship(back_populates="trip")


class CarpoolSeries(TimestampMixin, Base):
    """The thread that ties one carpool arrangement's months together.

    Deliberately only `(id, name)`: the car and the trip stay on each month, so
    an admin editing one month cannot leave the series disagreeing with its own
    rows, and a series whose last month is deleted holds no FK hostage.
    """

    __tablename__ = "carpool_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    groups: Mapped[list[CarpoolGroup]] = relationship(
        back_populates="series", order_by="CarpoolGroup.month.desc()"
    )


class CarpoolGroup(TimestampMixin, Base):
    __tablename__ = "carpool_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    car_id: Mapped[int] = mapped_column(
        ForeignKey("cars.id"), nullable=False, index=True
    )
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trips.id"), nullable=False, index=True
    )
    # Nullable on purpose: a group with no series is a standalone month, which
    # is exactly what the admin create form still produces.
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("carpool_series.id"), nullable=True, index=True
    )

    car: Mapped[Car] = relationship(back_populates="carpool_groups", lazy="joined")
    trip: Mapped[Trip] = relationship(back_populates="carpool_groups", lazy="joined")
    series: Mapped[CarpoolSeries | None] = relationship(
        back_populates="groups", lazy="joined"
    )
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="carpool_group",
        cascade="all, delete-orphan",
        order_by="Membership.id",
    )
    trip_logs: Mapped[list[TripLog]] = relationship(
        back_populates="carpool_group",
        cascade="all, delete-orphan",
        order_by="(TripLog.created_at.desc(), TripLog.id.desc())",
    )

    @property
    def series_key(self) -> tuple[str, int]:
        """Dashboard grouping key — a group with no series is its own series of one."""
        return ("series", self.series_id) if self.series_id else ("group", self.id)

    @property
    def trip_cost(self) -> Decimal:
        """Cost of a single leg: R/km x km."""
        return self.car.cost_per_km * self.trip.distance_km

    @property
    def total_trips(self) -> int:
        return sum((log.trip_count for log in self.trip_logs), 0)

    @property
    def monthly_tally(self) -> Decimal:
        return self.trip_cost * self.total_trips

    @property
    def split_total(self) -> Decimal:
        return sum((m.cost_split_percentage for m in self.memberships), ZERO)

    @property
    def splits_complete(self) -> bool:
        return abs(self.split_total - ONE) < SPLIT_TOLERANCE


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "carpool_group_id", name="uq_memberships_user_group"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    carpool_group_id: Mapped[int] = mapped_column(
        ForeignKey("carpool_groups.id"), nullable=False, index=True
    )
    cost_split_percentage: Mapped[Decimal] = mapped_column(Money(6, 4), nullable=False)

    user: Mapped[User] = relationship(back_populates="memberships", lazy="joined")
    carpool_group: Mapped[CarpoolGroup] = relationship(
        back_populates="memberships", lazy="joined"
    )

    @property
    def amount_owed(self) -> Decimal:
        return self.carpool_group.monthly_tally * self.cost_split_percentage


class TripLog(TimestampMixin, Base):
    """Append-only. One row per tap of + or -; the tally is their sum."""

    __tablename__ = "trip_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    carpool_group_id: Mapped[int] = mapped_column(
        ForeignKey("carpool_groups.id"), nullable=False, index=True
    )
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    carpool_group: Mapped[CarpoolGroup] = relationship(back_populates="trip_logs")
    recorded_by: Mapped[User | None] = relationship(
        back_populates="recorded_trip_logs",
        foreign_keys=[recorded_by_user_id],
        lazy="joined",
    )
