# CLAUDE.md — Carpool Cost Splitter

## Project Overview

A Hotwire Native Android app (with Rails backend) that allows carpool groups to track shared trips and automatically calculate how much each user owes based on their configured cost split percentage. At month-end, an admin can export a receipt PDF showing each member's balance.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Mobile framework | Hotwire Native (Android-first) |
| Backend | Ruby on Rails 8 (API + HTML views) |
| Authentication | Firebase Authentication (Google Sign-In) |
| Database | Firebase Firestore |
| Export | PDF receipt generated server-side (Prawn gem) |
| Native shell | Android Studio / Kotlin (minimal — Hotwire bridge only) |

---

## Data Model

### `User`
- `uid` (string) — Firebase Auth UID
- `display_name` (string)
- `email` (string)
- `cost_split_percentage` (decimal) — e.g. `0.30`, `0.40`
  - Must be set per carpool group membership (see `Membership`)

### `CarpoolGroup`
- `id`
- `name` (string)
- `month` (date) — e.g. `2024-06-01` (first of month, month-scoped)
- `car_id` (FK)
- `trip_id` (FK)

### `Car`
- `id`
- `name` (string) — e.g. "Toyota Corolla"
- `cost_per_km` (decimal) — e.g. `2.50`

### `Trip`
- `id`
- `name` (string) — e.g. "Morning Commute"
- `distance_km` (decimal) — distance of one trip leg

### `Membership` (join table: User ↔ CarpoolGroup)
- `user_id` (FK)
- `carpool_group_id` (FK)
- `cost_split_percentage` (decimal) — each user's share for this specific group
  - Validation: all memberships in a group must sum to `1.0` (100%)

### `TripLog`
- `id`
- `carpool_group_id` (FK)
- `recorded_by_user_id` (FK) — who tapped the + button
- `occurred_at` (datetime)
- `trip_count` (integer, default: 1) — always 1 per tap; aggregate for tally

---

## Core Business Logic

### Trip Cost Calculation

```
trip_cost = car.cost_per_km × trip.distance_km
monthly_tally = trip_cost × total_trip_logs_this_month
user_owes = monthly_tally × membership.cost_split_percentage
```

**Example:**
- Car: R2.50/km, Trip: 40km → trip cost = R100
- 10 trips logged → monthly tally = R1,000
- User A at 30% → owes R300
- User B at 40% → owes R400
- User C at 30% → owes R300

---

## Rails App Structure

```
app/
  models/
    user.rb
    carpool_group.rb
    car.rb
    trip.rb
    membership.rb
    trip_log.rb
  controllers/
    dashboard_controller.rb         # Home screen: user's groups
    carpool_groups_controller.rb    # Group detail + tally view
    trip_logs_controller.rb         # POST to log a trip (the + button)
    receipts_controller.rb          # Export receipt PDF
    sessions_controller.rb          # Firebase token verification + session
  views/
    dashboard/
      index.html.erb                # List of carpool groups
    carpool_groups/
      show.html.erb                 # Group detail: tally, members, + button
    receipts/
      show.pdf.prawn                # Receipt template
```

---

## Key Screens (Hotwire Native Views)

### 1. Login Screen
- Google Sign-In button (Firebase Auth)
- On success: Firebase ID token sent to Rails `/sessions` → Rails verifies token, creates session
- Native bridge component handles the Google Auth flow on Android

### 2. Dashboard (`/dashboard`)
- Lists the user's carpool groups
- Shows month, group name, car name
- Tap a group → navigate to group detail

### 3. Group Detail (`/carpool_groups/:id`)
- Shows group name, month, car, trip distance
- **Current tally**: total trips logged × cost per trip
- **Member list**: each member's name, percentage, and current amount owed
- Large **`+` FAB button** (Floating Action Button) — taps `POST /trip_logs`
  - Updates tally in real-time via Turbo Stream
- **Export Receipt** button → `GET /receipts/:carpool_group_id`

### 4. Receipt (`/receipts/:id`)
- Rendered server-side as a PDF
- Triggered via Hotwire Native's `open_external_url` bridge action
- Android will open or share the PDF natively

---

## Authentication Flow

1. Android native layer initiates Firebase Google Sign-In
2. On success, Firebase returns an `id_token`
3. Native bridge passes `id_token` to Rails via a `POST /sessions` request
4. Rails verifies the token with Firebase Admin SDK (`firebase_id_token` gem)
5. Rails creates a session and returns a cookie
6. All subsequent Hotwire requests use this cookie session

**Gem:** `firebase_id_token` for server-side token verification

---

## Receipt Export Format

Generated as a PDF using the `prawn` gem.

**Contents:**
```
Carpool Receipt — [Group Name]
Month: June 2024
Car: Toyota Corolla (R2.50/km)
Route: Morning Commute (40km per trip)
Total Trips: 10
Total Cost: R1,000.00
Generated: 2024-06-30 14:32

---

Member Breakdown:
  Alice Smith      30%    R300.00
  Bob Jones        40%    R400.00
  Carol White      30%    R300.00

---
Total accounted: R1,000.00
```

---

## Validation Rules

- `Membership` cost splits per group must sum to exactly 100%
- A `CarpoolGroup` must have at least 1 member before trip logs can be recorded
- `cost_per_km` and `distance_km` must be positive decimals
- A user can only belong to a group once (unique index on `memberships(user_id, carpool_group_id)`)
- `TripLog` is immutable once created (no editing or deletion via UI — append-only tally)

---

## Hotwire Native Android Notes

- Target: Android-first; iOS support is a future consideration
- Minimum Android SDK: API 26 (Android 8.0)
- Use `hotwire-native-android` library (official, not legacy `turbo-android`)
- Native bridge components needed:
  1. **Google Sign-In bridge** — handles Firebase Auth natively
  2. **PDF share bridge** — opens/shares the receipt PDF via Android's native share sheet
  3. **FAB styling bridge** (optional) — to give the `+` button a native Android FAB appearance
- All other screens are standard Hotwire web views

---

## Rails Configuration Notes

- Use `api: false` mode (full Rails with views, not API-only)
- Enable Turbo Streams for real-time tally updates after `+` is tapped
- CSRF: configure to accept requests from the Hotwire Native Android app
- Set `config.force_ssl = true` in production
- Firebase Admin credentials stored in Rails credentials (`rails credentials:edit`)

---

## Gems to Include

```ruby
gem "firebase_id_token"   # Firebase Auth token verification
gem "prawn"               # PDF generation for receipts
gem "prawn-table"         # Table support in Prawn PDFs
gem "hotwire-rails"       # Turbo + Stimulus
```

---

## Out of Scope (v1)

- Push notifications
- Offline support
- iOS app
- Admin UI for managing groups/cars/trips (set up via Rails console or seeds for v1)
- In-app payments
- Trip history editing or deletion
- Multi-currency support
