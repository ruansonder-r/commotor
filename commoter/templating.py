"""Jinja environment, view filters, and the flash message helpers."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import get_settings
from .security import csrf_token

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TURBO_STREAM_MIME = "text/vnd.turbo-stream.html"

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# --- Filters ----------------------------------------------------------------


def money(value: Decimal | float | None) -> str:
    """Rand amount, always two decimals: 1234.5 -> '1234.50'."""
    return f"{Decimal(str(value or 0)):.2f}"


def percent(value: Decimal | float | None) -> str:
    """0.3 -> '30'."""
    return f"{Decimal(str(value or 0)) * 100:.0f}"


def trim(value: Decimal | float | None) -> str:
    """Drop storage padding without slipping into scientific notation."""
    if value is None:
        return ""
    number = Decimal(str(value)).normalize()
    if number.as_tuple().exponent > 0:
        number = number.quantize(Decimal(1))
    return format(number, "f")


def month_label(value: dt.date | None) -> str:
    return value.strftime("%B %Y") if value else ""


def _as_utc(value: dt.datetime) -> dt.datetime:
    return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value


def time_ago(value: dt.datetime | None) -> str:
    """Port of Rails' `time_ago_in_words`."""
    if value is None:
        return ""
    seconds = max(0, (dt.datetime.now(dt.UTC) - _as_utc(value)).total_seconds())
    minutes = seconds / 60
    if minutes < 1:
        return "less than a minute"
    if minutes < 45:
        count = round(minutes)
        return f"{count} minute{'s' if count != 1 else ''}"
    hours = minutes / 60
    if hours < 24:
        count = round(hours)
        return f"about {count} hour{'s' if count != 1 else ''}"
    days = hours / 24
    if days < 30:
        count = round(days)
        return f"{count} day{'s' if count != 1 else ''}"
    months = days / 30
    if months < 12:
        count = round(months)
        return f"about {count} month{'s' if count != 1 else ''}"
    years = days / 365
    count = round(years)
    return f"about {count} year{'s' if count != 1 else ''}"


env.filters.update(
    money=money,
    percent=percent,
    trim=trim,
    month_label=month_label,
    time_ago=time_ago,
)


# --- Flash messages ---------------------------------------------------------

FLASH_KEY = "_flash"


def flash(request: Request, kind: str, message: str) -> None:
    request.session.setdefault(FLASH_KEY, []).append([kind, message])


def pop_flashes(request: Request) -> list[tuple[str, str]]:
    return [(k, m) for k, m in request.session.pop(FLASH_KEY, [])]


def redirect(
    request: Request,
    location: str,
    *,
    notice: str | None = None,
    alert: str | None = None,
) -> RedirectResponse:
    """303 so the browser re-issues the follow-up as GET, like Rails does."""
    if notice:
        flash(request, "notice", notice)
    if alert:
        flash(request, "alert", alert)
    return RedirectResponse(location, status_code=303)


# --- Rendering --------------------------------------------------------------


def _base_context(request: Request, user: Any = None) -> dict[str, Any]:
    settings = get_settings()
    return {
        "request": request,
        "current_user": user,
        "csrf_token": csrf_token(request),
        "flashes": pop_flashes(request),
        "path": request.url.path,
        "firebase_web_config": json.dumps(settings.firebase_web),
    }


def render(
    request: Request,
    template: str,
    *,
    user: Any = None,
    status_code: int = 200,
    **context: Any,
) -> HTMLResponse:
    body = env.get_template(template).render(_base_context(request, user) | context)
    return HTMLResponse(body, status_code=status_code)


def render_turbo_stream(
    request: Request, template: str, *, user: Any = None, **context: Any
) -> Response:
    body = env.get_template(template).render(_base_context(request, user) | context)
    return Response(body, media_type=TURBO_STREAM_MIME)


def wants_turbo_stream(request: Request) -> bool:
    return TURBO_STREAM_MIME in request.headers.get("accept", "")
