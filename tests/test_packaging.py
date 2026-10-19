"""Guards the dependency list Vercel actually installs from.

Vercel's Python builder runs uv against pyproject.toml and ignores
requirements.txt when pyproject.toml is present. A pyproject with no
`dependencies` key therefore installs nothing and the deploy fails at import
with ModuleNotFoundError, long after a green build. These tests make that
failure mode impossible to reintroduce quietly.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def _requirements() -> list[str]:
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    return sorted(
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith(("#", "-"))
    )


def test_pyproject_declares_the_runtime_dependencies():
    declared = _pyproject()["project"].get("dependencies")
    assert declared, (
        "pyproject.toml has no [project].dependencies — Vercel would install "
        "nothing and every request would fail with ModuleNotFoundError."
    )


def test_pyproject_and_requirements_agree():
    declared = sorted(_pyproject()["project"]["dependencies"])
    assert declared == _requirements(), (
        "pyproject.toml and requirements.txt have drifted. pyproject.toml is "
        "what Vercel installs from; requirements.txt is what local pip uses."
    )


def test_every_imported_third_party_package_is_declared():
    """The deploy-breaking case: an import with nothing declaring it."""
    distributions = {
        "fastapi": "fastapi",
        "starlette": "starlette",
        "jinja2": "Jinja2",
        "sqlalchemy": "SQLAlchemy",
        "jwt": "PyJWT",
        "cryptography": "cryptography",
        "httpx": "httpx",
        "reportlab": "reportlab",
        "itsdangerous": "itsdangerous",
        "psycopg": "psycopg",
        "multipart": "python-multipart",
        "alembic": "alembic",
    }
    declared = {
        dep.split("==")[0].split("[")[0].lower()
        for dep in _pyproject()["project"]["dependencies"]
    }

    source = "\n".join(
        path.read_text()
        for path in (ROOT / "commoter").rglob("*.py")
    ) + (ROOT / "api" / "index.py").read_text()

    for module, distribution in distributions.items():
        if f"import {module}" in source or f"from {module}" in source:
            assert distribution.lower() in declared, (
                f"commoter imports `{module}` but `{distribution}` is not in "
                f"pyproject.toml's dependencies"
            )


def test_vercel_json_has_no_catch_all_rewrite_to_the_entrypoint():
    """Vercel detects FastAPI natively and routes with the original path.

    A catch-all rewrite to the entrypoint made it hand the app the *rewritten*
    path instead, so every request arrived as `/api/index`, matched no route,
    and rendered the 404 page on an otherwise healthy deployment.
    """
    config = json.loads((ROOT / "vercel.json").read_text())
    for rewrite in config.get("rewrites", []):
        assert not (
            rewrite.get("source", "").strip("/") in ("(.*)", ":path*", "(.*)/")
            and "api/index" in rewrite.get("destination", "")
        ), (
            "A catch-all rewrite to api/index makes FastAPI see `/api/index` "
            "for every request. Vercel routes to the detected entrypoint on "
            "its own; the rewrite is not needed."
        )
