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

### Remaining steps

**1. Accept the Neon marketplace terms** (one-off, needs a browser — a legal
acceptance nobody can click on your behalf):

<https://vercel.com/ruansonderrs-projects/~/integrations/accept-terms/neon>

Then provision the database:

```bash
vercel integration add neon \
  --plan free_v3 --name commoter-db \
  -m region=fra1 -m auth=false -m realtime=false \
  -e production -e preview --no-env-pull
```

`auth=false` because sign-in is Firebase's job, and `region=fra1` to match
`regions` in `vercel.json`. If you move the database, move the function too.
This sets `DATABASE_URL` automatically.

**2. Add the Firebase values.** These are not recoverable from this repo — the
Rails credentials were encrypted and `config/master.key` was never on this
machine. Get them from the Firebase console under
**Project settings → Your apps → Web app**:

```bash
vercel env add FIREBASE_PROJECT_ID production
vercel env add FIREBASE_WEB_API_KEY production
vercel env add FIREBASE_WEB_AUTH_DOMAIN production
vercel env add FIREBASE_WEB_APP_ID production
vercel env add FIREBASE_WEB_MESSAGING_SENDER_ID production
vercel env add FIREBASE_WEB_STORAGE_BUCKET production
vercel env add ADMIN_EMAILS production     # your sign-in email, to reach /admin
```

The web config values are public by design — they ship to the browser either
way, so they are not secrets. `FIREBASE_PROJECT_ID` is the one that matters for
security: it is the audience the server checks every ID token against.

**3. Run the migration** from here, against the **direct** (unpooled) Neon URL —
functions are ephemeral, so nothing migrates at boot:

```bash
vercel env pull .env.production --environment=production
DATABASE_URL="<direct neon url>" .venv/bin/alembic upgrade head
DATABASE_URL="<direct neon url>" .venv/bin/python -m scripts.seed   # optional
```

The app itself connects with the **pooled** URL (host contains `-pooler`) and
`NullPool`, leaving pooling to Neon's PgBouncer.

**4. Deploy:**

```bash
vercel deploy --prod
```

**5. Authorise the domain in Firebase.** In the console under
**Authentication → Settings → Authorized domains**, add
`commute.ruansonder-r.com`. Until you do, Google sign-in fails with
`auth/unauthorized-domain` — the single most common first-deploy failure. Add
the `*.vercel.app` preview domain too if you want sign-in working on previews.

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
