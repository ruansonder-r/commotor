# Commoter

Carpool groups track shared trips and split the cost. Members tap **+** to log a
trip; the tally and each member's balance update live. At month-end anyone in
the group can export a PDF receipt.

Python rewrite of the original Rails 8 app, built to deploy on Vercel.

| Layer | Choice |
|---|---|
| Web framework | FastAPI (ASGI), served as a single Vercel Function |
| Templates | Jinja2, server-rendered HTML |
| Front-end | Turbo 8 (vendored) + ~150 lines of plain JS. No build step. |
| ORM / migrations | SQLAlchemy 2 + Alembic |
| Database | Postgres (Neon) in production, SQLite locally |
| Auth | Firebase Google Sign-In, ID token verified server-side |
| PDF | ReportLab |
| Install | Progressive Web App (manifest + service worker) |

---

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

cp .env.example .env          # fill in the Firebase values
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed

.venv/bin/uvicorn commoter.main:app --reload --port 8000
```

With no `DATABASE_URL` set it uses a local SQLite file, so the only variables
you strictly need for a first run are the Firebase ones.

### Tests

```bash
.venv/bin/pytest            # 60 tests, ~1s, no network or database required
```

Covers the cost arithmetic, every validation rule, the full request surface
(auth, scoping, CSRF, Turbo Streams, PDF, admin), Firebase token verification
including alg-confusion and wrong-audience attacks, and a check that the
migrations still build exactly the schema the models describe.

---

## Deploying to Vercel

The project is already linked: **`ruansonderrs-projects/commoter`**, connected
to the `ruansonder-r/commotor` GitHub repo, with the function pinned to `fra1`
(see `vercel.json`) to sit next to the database.

It will serve at **<https://commute.ruansonder-r.com>**.

Already done:

- [x] `vercel link` — project created and linked
- [x] `APP_ENV=production` set on production and preview
- [x] `SESSION_SECRET` set on production and preview (a different secret each,
      so a preview deploy cannot mint a production session)
- [x] `commute.ruansonder-r.com` attached and DNS-verified. The domain is
      registered with Vercel on Vercel nameservers and already has a wildcard
      ALIAS, so no record needed adding and the certificate is automatic. The
      apex and `www` stay on `photo-portfolio-host-19ab`, untouched.

- [x] Neon provisioned (`commoter-db`, free plan, `eu-central-1` — matching the
      `fra1` function region so queries do not cross a continent)
- [x] Firebase values set on production
- [x] `alembic upgrade head` applied to Neon

### Connection strings

The Neon integration sets **both** URLs for you — there is nothing to look up in
the Neon console:

| Variable | Host | Use it for |
|---|---|---|
| `DATABASE_URL` | `...-pooler...` | the app (what `db.py` reads) |
| `DATABASE_URL_UNPOOLED` | no `-pooler` | migrations, `pg_dump`, replication |

The pooled URL goes through PgBouncer in transaction mode, which has no stable
session state — so schema migrations, dumps and `LISTEN`/`NOTIFY` need the
direct one. To get it:

```bash
vercel env pull .env.production --environment=production
grep DATABASE_URL_UNPOOLED .env.production
```

Then run migrations with it:

```bash
DATABASE_URL="<DATABASE_URL_UNPOOLED value>" .venv/bin/alembic upgrade head
```

(Verified: repeated parameterised queries across commits work fine over the
pooled URL — Neon's PgBouncer supports protocol-level prepared statements, so
psycopg3 needs no `prepare_threshold` workaround.)

### Remaining steps

**1. Authorise the domain in Firebase.** In the console under
**Authentication → Settings → Authorized domains**, add
`commute.ruansonder-r.com`. Until you do, Google sign-in fails with
`auth/unauthorized-domain` — the single most common first-deploy failure.

**2. Deploy:**

```bash
vercel deploy --prod      # or push master, which deploys automatically
```

**3. Sign in once**, then add a car, trip, group and memberships under
`/admin`. Splits must total 100% before trips can be logged. `scripts/seed.py`
can pre-fill a car/trip/group if you would rather start from the old seed data.

### Known gaps in the current setup

- **`ADMIN_EMAILS` and the `FIREBASE_*` vars are set on Production only.**
  Preview deployments will build but sign-in will fail on them. Copy them to
  Preview (`vercel env add <NAME> preview`) if you want working previews, and
  add the `*.vercel.app` domain to Firebase's authorized domains too.
- **There is a stray environment variable literally named `commoter`** on
  Production. It looks like a mistyped `vercel env add` — the app never reads
  it. Remove it with `vercel env rm commoter production`.

### A note on the GitHub connection

Linking connected the repo, so Vercel now builds on push: a push to any branch
creates a preview deployment, and a push to `master` deploys to production at
`commute.ruansonder-r.com`. Nothing has been pushed yet — finish steps 1–3
first, or the domain will go live pointing at an app with no database.

---

## How it fits together

```
api/index.py              Vercel entrypoint; everything else is a static file
vercel.json               rewrites /(.*) to that function
commoter/
  config.py               env-var settings, Postgres URL normalisation
  db.py                   engine, session factory, portable Decimal column
  models.py               6 models + the derived cost properties
  validation.py           business rules (ported ActiveRecord validations)
  security.py             Firebase token verification, session auth, CSRF
  templating.py           Jinja env, view filters, flash messages
  pdf.py                  ReportLab receipt
  routers/                one module per area; admin/ is one CRUD factory
  templates/              21 Jinja templates
public/                   served by Vercel's CDN, never through the function
migrations/               Alembic
```

### Cost calculation

```
trip_cost     = car.cost_per_km x trip.distance_km
monthly_tally = trip_cost x sum(trip_logs.trip_count)
user_owes     = monthly_tally x membership.cost_split_percentage
```

All of it is `Decimal` arithmetic end to end. SQLite has no decimal type, so the
`Money` column in `db.py` stores the text form there and real `NUMERIC` on
Postgres — dev and production agree to the cent.

### Rules worth knowing

- A group's membership splits must total 100% (±0.001) before any trip can be
  logged, and a group needs at least one member.
- `TripLog` is append-only. Tapping **−** writes a `-1` row; nothing is deleted,
  and the history shows every tap.
- `cost_per_km` and `distance_km` must be positive.
- A user can only join a group once (enforced by a unique constraint *and* in
  validation, so the user gets a message rather than a 500).
- Cars and trips still referenced by a group cannot be deleted.
- Every group lookup is scoped through membership — a non-member gets a 404.

---

## Notable differences from the Rails version

- **No Hotwire Native shell.** This is a web/PWA build: the receipt downloads
  through a normal `Content-Disposition: attachment` rather than the native
  share-sheet bridge, and the native bridge attributes are gone. Turbo itself
  stays, so the tally still updates without a page reload.
- **Admin is gated.** In the Rails app `Admin::BaseController` only required a
  login, so any signed-in user could edit cars, groups and splits. There is now
  an `is_admin` flag, granted via the `ADMIN_EMAILS` environment variable on
  next sign-in. Worth knowing about if you expected the old behaviour.
- **No Redis.** It only cached Google's signing certificates; that is now an
  in-process cache that survives warm function invocations.
- **Stimulus is gone**, replaced by delegated event listeners that survive
  Turbo's body swaps.

### Known gap

There is no Content-Security-Policy header. The Rails app had none either (the
initializer was entirely commented out). Adding one here means allow-listing
`gstatic.com` for the Firebase SDK plus its auth iframe and token endpoints —
worth doing, but it needs testing against a real Firebase project to avoid
silently breaking sign-in.
