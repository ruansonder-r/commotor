"""End-to-end request tests across the ported routes."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from commoter.models import Car, Membership, TripLog

from .conftest import csrf_token_from


def test_unauthenticated_visitors_are_sent_to_sign_in(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/session/new"


def test_sign_in_page_renders_without_a_session(client):
    response = client.get("/session/new")
    assert response.status_code == 200
    assert "Sign in with Google" in response.text


def test_health_check_needs_no_session(client):
    assert client.get("/up").json() == {"status": "ok"}


def test_dashboard_shows_only_the_users_own_groups(client, db, make, sign_in):
    alice = make.user(db, name="Alice")
    bob = make.user(db, name="Bob")
    mine = make.group(db, name="My Commute")
    theirs = make.group(db, name="Their Commute")
    make.membership(db, alice, mine, "1.0")
    make.membership(db, bob, theirs, "1.0")
    sign_in(alice)

    body = client.get("/dashboard").text
    assert "My Commute" in body
    assert "Their Commute" not in body


def test_a_non_member_cannot_open_a_group(client, db, make, sign_in):
    outsider = make.user(db, name="Outsider")
    group = make.group(db)
    make.membership(db, make.user(db), group, "1.0")
    sign_in(outsider)

    response = client.get(f"/carpool_groups/{group.id}")
    assert response.status_code == 404


def test_group_page_shows_the_tally_and_member_breakdown(client, db, make, sign_in):
    group = make.group(db, cost_per_km="2.50", distance_km="40")
    alice = make.user(db, name="Alice")
    bob = make.user(db, name="Bob")
    make.membership(db, alice, group, "0.60")
    make.membership(db, bob, group, "0.40")
    for _ in range(4):
        make.trip_log(db, group, alice)
    sign_in(alice)

    body = client.get(f"/carpool_groups/{group.id}").text
    assert "R400.00" in body  # 2.50 x 40 x 4
    assert "R240.00" in body  # Alice's 60%
    assert "R160.00" in body  # Bob's 40%


def test_logging_a_trip_returns_a_turbo_stream(client, db, make, sign_in):
    group = make.group(db, cost_per_km="1.00", distance_km="10")
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    sign_in(user)

    token = csrf_token_from(client)
    response = client.post(
        f"/carpool_groups/{group.id}/trip_logs",
        data={"_csrf": token},
        headers={"Accept": "text/vnd.turbo-stream.html"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/vnd.turbo-stream.html")
    assert f'target="tally_carpool_group_{group.id}"' in response.text
    assert "R10.00" in response.text

    db.expire_all()
    assert db.scalar(select(TripLog).where(TripLog.carpool_group_id == group.id))


def test_logging_without_turbo_redirects_back(client, db, make, sign_in):
    group = make.group(db)
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    sign_in(user)

    token = csrf_token_from(client)
    response = client.post(
        f"/carpool_groups/{group.id}/trip_logs",
        data={"_csrf": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/carpool_groups/{group.id}"


def test_logging_is_blocked_until_splits_total_one_hundred(client, db, make, sign_in):
    group = make.group(db)
    user = make.user(db)
    make.membership(db, user, group, "0.50")
    sign_in(user)

    token = csrf_token_from(client)
    response = client.post(
        f"/carpool_groups/{group.id}/trip_logs", data={"_csrf": token}
    )

    assert "sum to 100%" in response.text
    db.expire_all()
    assert db.scalars(select(TripLog)).all() == []


def test_decrement_will_not_go_below_zero(client, db, make, sign_in):
    group = make.group(db)
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    sign_in(user)

    token = csrf_token_from(client)
    response = client.post(
        f"/carpool_groups/{group.id}/trip_logs/decrement", data={"_csrf": token}
    )

    assert "Already at zero trips." in response.text
    db.expire_all()
    assert db.scalars(select(TripLog)).all() == []


def test_decrement_after_a_log_works(client, db, make, sign_in):
    group = make.group(db)
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    make.trip_log(db, group, user)
    sign_in(user)

    token = csrf_token_from(client)
    client.post(f"/carpool_groups/{group.id}/trip_logs/decrement", data={"_csrf": token})

    db.expire_all()
    db.refresh(group)
    assert group.total_trips == 0
    assert len(group.trip_logs) == 2  # append-only: nothing was deleted


def test_a_post_without_a_csrf_token_is_rejected(client, db, make, sign_in):
    group = make.group(db)
    user = make.user(db)
    make.membership(db, user, group, "1.0")
    sign_in(user)
    csrf_token_from(client)  # establish a session that does have a token

    response = client.post(
        f"/carpool_groups/{group.id}/trip_logs", data={}, follow_redirects=False
    )

    assert response.status_code == 303
    db.expire_all()
    assert db.scalars(select(TripLog)).all() == []


def test_receipt_renders_a_pdf(client, db, make, sign_in):
    group = make.group(db, name="Morning Crew", cost_per_km="2.50", distance_km="40")
    alice = make.user(db, name="Alice")
    make.membership(db, alice, group, "1.0")
    make.trip_log(db, group, alice)
    sign_in(alice)

    response = client.get(f"/carpool_groups/{group.id}/receipt")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert "receipt_morning-crew_May_2026.pdf" in response.headers["content-disposition"]


# --- Admin ------------------------------------------------------------------


def test_admin_is_closed_to_ordinary_members(client, db, make, sign_in):
    sign_in(make.user(db))
    response = client.get("/admin/cars", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_the_admin_tab_is_hidden_from_ordinary_members(client, db, make, sign_in):
    user = make.user(db)
    group = make.group(db)
    make.membership(db, user, group, "1.0")
    sign_in(user)

    assert "Config Stuff" not in client.get("/dashboard").text


def test_an_admin_can_create_a_car(client, db, make, sign_in):
    sign_in(make.user(db, admin=True))
    token = csrf_token_from(client, "/admin/cars")

    response = client.post(
        "/admin/cars",
        data={"_csrf": token, "name": "Polo Vivo", "cost_per_km": "2.10"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    car = db.scalar(select(Car).where(Car.name == "Polo Vivo"))
    assert car is not None and car.cost_per_km == Decimal("2.1000")


def test_an_invalid_car_re_renders_the_form_with_errors(client, db, make, sign_in):
    sign_in(make.user(db, admin=True))
    token = csrf_token_from(client, "/admin/cars")

    response = client.post(
        "/admin/cars", data={"_csrf": token, "name": "Broken", "cost_per_km": "-1"}
    )

    assert response.status_code == 422
    assert "Cost per km must be greater than 0" in response.text
    assert 'value="Broken"' in response.text  # the submitted value is preserved
    assert db.scalars(select(Car)).all() == []


def test_a_car_still_in_use_cannot_be_deleted(client, db, make, sign_in):
    group = make.group(db)
    sign_in(make.user(db, admin=True))
    token = csrf_token_from(client, "/admin/cars")

    client.post(f"/admin/cars/{group.car_id}/delete", data={"_csrf": token})

    db.expire_all()
    assert db.get(Car, group.car_id) is not None


def test_an_admin_can_add_a_membership(client, db, make, sign_in):
    group = make.group(db)
    member = make.user(db, name="Bob")
    sign_in(make.user(db, admin=True))
    token = csrf_token_from(client, "/admin/memberships")

    client.post(
        "/admin/memberships",
        data={
            "_csrf": token,
            "user_id": str(member.id),
            "carpool_group_id": str(group.id),
            "cost_split_percentage": "0.5",
        },
    )

    saved = db.scalar(select(Membership).where(Membership.user_id == member.id))
    assert saved is not None and saved.cost_split_percentage == Decimal("0.5000")


def test_admin_root_redirects_to_cars(client, db, make, sign_in):
    sign_in(make.user(db, admin=True))
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/cars"


def test_unknown_paths_render_the_404_page(client, db, make, sign_in):
    sign_in(make.user(db))
    response = client.get("/nope")
    assert response.status_code == 404
    assert "isn" in response.text
