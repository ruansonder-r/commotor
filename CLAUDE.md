# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Commoter** is a Hotwire Native Android app (Rails 8 backend) for carpool groups to track shared trips and split costs. Users log trips via a `+` FAB; an admin exports a PDF receipt at month-end showing each member's balance.

---

## Common Commands

```bash
# Setup
bundle install
bin/rails db:create db:migrate db:seed

# Run the server
bin/rails server

# Run all tests
bin/rails test

# Run a single test file
bin/rails test test/models/membership_test.rb

# Run a single test by line number
bin/rails test test/models/membership_test.rb:42

# Lint (if rubocop is added)
bundle exec rubocop

# Rails credentials (Firebase Admin credentials live here)
bin/rails credentials:edit
```

---

## Architecture

**Full-stack Rails (not API-only).** Views are served as HTML and driven by Hotwire (Turbo + Stimulus). The Android app is a thin Hotwire Native shell — almost all UI logic lives in Rails views, with three native bridge components for auth, PDF sharing, and the FAB.

### Authentication
Firebase Google Sign-In is handled natively on Android. The ID token is posted to `POST /sessions`, verified server-side via the `firebase_id_token` gem, and exchanged for a Rails cookie session. All subsequent requests are standard cookie-authenticated Hotwire requests.

### Trip Cost Calculation
```
trip_cost    = car.cost_per_km × trip.distance_km
monthly_cost = trip_cost × count(TripLog) for the month
user_owes    = monthly_cost × membership.cost_split_percentage
```

### Key Data Relationships
- `CarpoolGroup` belongs to a `Car` and a `Trip`, and is scoped to a calendar month.
- `Membership` is the join table between `User` and `CarpoolGroup`. It holds each user's `cost_split_percentage` — **all memberships in a group must sum to exactly 1.0**.
- `TripLog` is append-only. Each tap of the `+` button creates one record; tallies are computed by aggregating logs, never edited.
- `cost_split_percentage` on `User` is a user-level default; the authoritative value per group is on `Membership`.

### Real-time Updates
After `POST /trip_logs`, the tally on the group detail page updates via a Turbo Stream response — no page reload.

### PDF Receipt
Generated server-side by `prawn` + `prawn-table` in `receipts_controller.rb`. Rendered via `show.pdf.prawn`. The Hotwire Native PDF bridge then opens/shares the file via Android's native share sheet.

### Android Bridge Components
Three native bridge components are needed:
1. **Google Sign-In bridge** — Firebase Auth flow
2. **PDF share bridge** — opens the receipt via Android share sheet (`open_external_url` bridge action)
3. **FAB styling bridge** (optional) — native Android FAB appearance for the `+` button

### CSRF
Must be configured to accept requests from the Hotwire Native Android WebView.

---

## Validation Rules Worth Knowing

- `Membership` splits per group must sum to `1.0` (100%) — enforced at the model level.
- A group needs at least 1 member before `TripLog` records can be created.
- `cost_per_km` and `distance_km` must be positive decimals.
- A user can only be a member of a group once (`unique index on memberships(user_id, carpool_group_id)`).
- `TripLog` records are immutable — no update or destroy routes.

---

## Rails Configuration Notes

- `api: false` (full Rails with views)
- `config.force_ssl = true` in production
- Firebase Admin credentials stored via `rails credentials:edit`
- Minimum Android SDK target: API 26 (Android 8.0)
- Use `hotwire-native-android` (not the legacy `turbo-android`)
