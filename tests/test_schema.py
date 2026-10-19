"""Guards against the migrations and the models drifting apart."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

import commoter.models  # noqa: F401  (registers tables on Base.metadata)
from commoter.db import Base

ROOT = Path(__file__).resolve().parent.parent

# SQLite reflection cannot report server defaults faithfully, so comparing them
# produces noise. Added/removed/renamed tables, columns and indexes are the
# drift that actually matters.
STRUCTURAL = {
    "add_table",
    "remove_table",
    "add_column",
    "remove_column",
    "add_index",
    "remove_index",
    "add_constraint",
    "remove_constraint",
    "modify_nullable",
}


def test_migrations_build_exactly_the_model_schema(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    engine = create_engine(url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diffs = compare_metadata(context, Base.metadata)

    drift = [d for d in diffs if _kind(d) in STRUCTURAL]
    assert drift == [], f"migrations are out of step with the models: {drift}"


def _kind(diff) -> str:
    # Diffs are either a tuple whose first item names the change, or a list of
    # such tuples when several constraints move together.
    if isinstance(diff, list):
        return _kind(diff[0]) if diff else ""
    return diff[0] if isinstance(diff, tuple) else ""


def test_production_without_a_database_url_fails_loudly(monkeypatch):
    """A SQLite fallback on Vercel's read-only filesystem fails confusingly."""
    import pytest

    from commoter.config import Settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        Settings()
