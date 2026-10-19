"""Runtime configuration, read from the environment.

Mirrors what used to live in Rails credentials + config/environments. Everything
is an env var so it works identically on a laptop and on Vercel.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader for local development. Vercel injects real env vars."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()


def _normalise_database_url(url: str) -> str:
    """Neon/Vercel hand out `postgres://`; SQLAlchemy 2 wants an explicit driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings:
    def __init__(self) -> None:
        self.env = os.environ.get("APP_ENV", "development")

        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            if self.env == "production":
                # Falling back to SQLite here would "work" until the first write
                # hit the read-only function filesystem, which is a baffling way
                # to find out the database was never connected.
                raise RuntimeError(
                    "DATABASE_URL is not set. Connect the Neon integration to "
                    "this project (vercel integration add neon) and redeploy."
                )
            database_url = f"sqlite:///{ROOT / 'commoter.db'}"
        self.database_url = _normalise_database_url(database_url)
        self.session_secret = os.environ.get("SESSION_SECRET", "")
        self.firebase_project_id = os.environ.get("FIREBASE_PROJECT_ID", "commoter")

        # Public Firebase web config — safe to ship to the browser, it is not a secret.
        self.firebase_web = {
            "apiKey": os.environ.get("FIREBASE_WEB_API_KEY", ""),
            "authDomain": os.environ.get("FIREBASE_WEB_AUTH_DOMAIN", ""),
            "projectId": os.environ.get("FIREBASE_WEB_PROJECT_ID")
            or self.firebase_project_id,
            "storageBucket": os.environ.get("FIREBASE_WEB_STORAGE_BUCKET", ""),
            "messagingSenderId": os.environ.get("FIREBASE_WEB_MESSAGING_SENDER_ID", ""),
            "appId": os.environ.get("FIREBASE_WEB_APP_ID", ""),
        }

        # Bootstrap list: these emails get is_admin on sign-in. Comma separated.
        self.admin_emails = {
            e.strip().lower()
            for e in os.environ.get("ADMIN_EMAILS", "").split(",")
            if e.strip()
        }

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def resolved_session_secret(self) -> str:
        if self.session_secret:
            return self.session_secret
        if self.is_production:
            raise RuntimeError(
                "SESSION_SECRET must be set in production — without it, every "
                "deploy would silently invalidate all sessions."
            )
        return "dev-only-insecure-secret"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
