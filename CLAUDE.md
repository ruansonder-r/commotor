# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Project Overview

**Commoter** is a FastAPI web app (deployed on Vercel) for carpool groups to
track shared trips and split costs. Members log trips with a `+` button; anyone
in a group can export a PDF receipt showing each member's balance.

It is a Python rewrite of an earlier Rails 8 + Hotwire Native Android app. The
native shell was dropped — this is a web/PWA build. Turbo is still used for the
live tally update, but there is no Android project and no bridge components.

---

## Common Commands

```bash
# Setup
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env

# Database
.venv/bin/alembic upgrade head
.venv/bin/alembic revision --autogenerate -m "describe the change"
.venv/bin/python -m scripts.seed

# Run the server
.venv/bin/uvicorn commoter.main:app --reload --port 8000

# Tests
.venv/bin/pytest
.venv/bin/pytest tests/test_validation.py
.venv/bin/pytest tests/test_validation.py::test_car_name_is_required

# Deploy
vercel deploy --prod
```

---

## Architecture

**Server-rendered HTML, no build step.** FastAPI returns Jinja2 templates.
Turbo 8 is vendored at `public/assets/turbo.js`; front-end behaviour is ~150
lines of plain JS in `public/assets/app.js` using delegated listeners (so it
survives Turbo body swaps). There is no bundler, no npm, no Stimulus.

### Deployment shape

`api/index.py` imports the app; `vercel.json` rewrites `/(.*)` to it. Vercel
checks the filesystem before rewrites, so everything in `public/` is served by
the CDN and never reaches the function. Put static assets there, not in
`commoter/`.

Functions are ephemeral: **never run migrations at boot.** Run
`alembic upgrade head` from a developer machine against the direct (unpooled)
database URL. The app connects with the pooled URL and `NullPool`.

### Authentication

Firebase Google Sign-In in the browser. The ID token is posted to
`POST /session`, verified in `security.py` against Google's x509 certs (PyJWT,
certs cached in module scope), and exchanged for a signed-cookie session
(Starlette `SessionMiddleware`). That route is deliberately CSRF-exempt — the
token is itself a signed identity assertion.

Admin access requires `User.is_admin`, granted by listing an email in the
`ADMIN_EMAILS` env var; it is applied on that user's next sign-in.

### Trip cost calculation

```
trip_cost     = car.cost_per_km x trip.distance_km
monthly_tally = trip_cost x sum(trip_logs.trip_count)
user_owes     = monthly_tally x membership.cost_split_percentage
```

All `Decimal`, never float. The `Money` type in `db.py` stores text on SQLite
and `NUMERIC` on Postgres so dev and production agree exactly — if you add a
money column, use `Money()`, not `Numeric`.

### Key data relationships

- `CarpoolGroup` belongs to a `Car` and a `Trip`, scoped to a calendar month.
- `Membership` joins `User` and `CarpoolGroup` and holds that user's
  `cost_split_percentage` — **all memberships in a group must sum to 1.0**.
- `TripLog` is append-only. Each tap writes one row (`-1` for the minus button);
  tallies are aggregated from the rows and nothing is ever edited or deleted.
- Derived money values are computed in Python from loaded relationships, not SQL
  aggregates, so they stay exact Decimals.

### Live updates

`POST /carpool_groups/{id}/trip_logs` returns a Turbo Stream
(`text/vnd.turbo-stream.html`) when the request accepts one, replacing the tally
and history frames; otherwise it redirects. Both paths are tested.

### Admin CRUD

The four admin resources are generated from one `AdminResource` description in
`routers/admin.py`. To add a resource, add a `register(AdminResource(...))` call
plus `index.html` and `form.html` under `templates/admin/<slug>/`.

---

## Conventions

- **Validation lives in `validation.py`**, raising `ValidationError` with
  Rails-style messages ("Cost per km must be greater than 0"). Routers catch it
  and re-render the form with a 422 and the submitted values preserved.
- **Control flow via exceptions**: `RedirectError` (auth bounces),
  `NotFoundError` (404), handled centrally in `main.py`.
- **Every group lookup goes through `load_group_for_user`** so a non-member gets
  a 404 rather than someone else's data.
- **CSRF**: every state-changing form posts a `_csrf` hidden field validated by
  the `verify_csrf` dependency. Destructive actions use `POST .../delete`
  (HTML forms cannot issue DELETE), not a method override.

## Validation Rules Worth Knowing

- Membership splits per group must sum to `1.0` (±0.001 tolerance, so thirds work).
- A group needs at least one member, with splits totalling 100%, before any
  `TripLog` can be created.
- `cost_per_km` and `distance_km` must be positive decimals.
- A user can be a member of a group only once (unique constraint + validation).
- `TripLog` records are immutable — no update or delete routes exist.
- Cars and trips referenced by a group cannot be deleted.

## Testing

`tests/conftest.py` sets every env var **before** importing `commoter.config`,
because settings are cached and the engine is built at import time. Add new env
vars there too. Tests use SQLite, a `make` factory fixture, and a `sign_in`
fixture that overrides the `get_current_user` dependency. `test_schema.py` fails
if the migrations and models drift apart — regenerate the migration rather than
editing the models alone.
