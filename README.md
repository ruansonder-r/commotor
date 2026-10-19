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

### 1. Database

Provision Neon from the Vercel Marketplace and link it to the project:

```bash
vercel link
vercel integration add neon
```

That sets `DATABASE_URL` automatically. **Use the pooled connection string**
(the host contains `-pooler`) — functions open a fresh connection per cold
start, so PgBouncer does the pooling rather than the app.

### 2. Environment variables

```bash
vercel env add SESSION_SECRET production     # python -c "import secrets; print(secrets.token_urlsafe(48))"
vercel env add APP_ENV production            # value: production
vercel env add FIREBASE_PROJECT_ID production
vercel env add FIREBASE_WEB_API_KEY production
vercel env add FIREBASE_WEB_AUTH_DOMAIN production
vercel env add FIREBASE_WEB_APP_ID production
vercel env add FIREBASE_WEB_MESSAGING_SENDER_ID production
vercel env add FIREBASE_WEB_STORAGE_BUCKET production
vercel env add ADMIN_EMAILS production       # comma-separated; grants admin on next sign-in
```

`APP_ENV=production` is what turns on `Secure` session cookies and HSTS, and
makes a missing `SESSION_SECRET` a hard startup error instead of a silent
insecure default.

### 3. Migrations

Functions are ephemeral, so migrations are not run at boot. Run them from your
machine against the **unpooled** (direct) Neon URL:

```bash
vercel env pull .env.production
DATABASE_URL="<direct neon url>" .venv/bin/alembic upgrade head
DATABASE_URL="<direct neon url>" .venv/bin/python -m scripts.seed   # optional
```

### 4. Deploy

```bash
vercel deploy --prod
```

### 5. Firebase

In the Firebase console → **Authentication → Settings → Authorized domains**,
add the Vercel domain. Google sign-in fails with `auth/unauthorized-domain`
until you do, and that is the single most common first-deploy failure.

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
