"""Database engine, session factory, and the portable decimal column type."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from sqlalchemy import Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

from .config import get_settings

settings = get_settings()

if settings.is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    # Serverless: hand pooling to Neon's PgBouncer rather than holding sockets
    # open inside a function instance that may be frozen at any moment.
    engine = create_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Money(TypeDecorator):
    """NUMERIC on Postgres, TEXT on SQLite, `Decimal` in Python either way.

    SQLite has no real decimal type, so SQLAlchemy would otherwise round-trip
    these through a float and quietly lose cents. Storing the text form keeps
    dev/test arithmetic identical to production.
    """

    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int = 12, scale: int = 4) -> None:
        self._precision = precision
        self._scale = scale
        super().__init__(precision=precision, scale=scale, asdecimal=True)

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(40))
        return dialect.type_descriptor(
            Numeric(self._precision, self._scale, asdecimal=True)
        )

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        quantised = Decimal(str(value)).quantize(Decimal(1).scaleb(-self._scale))
        return str(quantised) if dialect.name == "sqlite" else quantised

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(str(value))


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
