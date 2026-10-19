"""Admin CRUD for cars, trips, groups and memberships.

The four resources were four near-identical Rails controllers. They are built
from one `AdminResource` description here instead: the only things that actually
differ are the model, how a submitted form is validated, and what extra data the
form needs for its select boxes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import NotFoundError, ValidationError
from ..models import Car, CarpoolGroup, CarpoolSeries, Membership, Trip, User
from ..security import require_admin, verify_csrf
from ..templating import redirect, render
from ..validation import (
    assert_removable,
    validate_car_fields,
    validate_carpool_group_fields,
    validate_membership_fields,
    validate_trip_fields,
)

router = APIRouter(prefix="/admin")


@dataclass(frozen=True)
class AdminResource:
    slug: str
    singular: str
    model: type
    parse: Callable[[Session, Any, int | None], dict]
    to_values: Callable[[Any], dict]
    listing: Callable[[Session], list]
    form_context: Callable[[Session], dict] = field(default=lambda db: {})
    guard_delete: Callable[[Any], None] | None = None

    @property
    def base_path(self) -> str:
        return f"/admin/{self.slug}"


def _find(db: Session, resource: AdminResource, record_id: int):
    record = db.get(resource.model, record_id)
    if record is None:
        raise NotFoundError(f"No {resource.singular} with id {record_id}")
    return record


def register(resource: AdminResource) -> None:
    index_tpl = f"admin/{resource.slug}/index.html"
    form_tpl = f"admin/{resource.slug}/form.html"

    @router.get(f"/{resource.slug}")
    async def index(
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        return render(
            request,
            index_tpl,
            user=admin,
            records=resource.listing(db),
            section=resource.slug,
        )

    @router.get(f"/{resource.slug}/new")
    async def new(
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        return render(
            request,
            form_tpl,
            user=admin,
            section=resource.slug,
            action=resource.base_path,
            heading=f"Add {resource.singular}",
            values={},
            errors=[],
            **resource.form_context(db),
        )

    @router.post(f"/{resource.slug}", dependencies=[Depends(verify_csrf)])
    async def create(
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        form = await request.form()
        try:
            attributes = resource.parse(db, form, None)
        except ValidationError as exc:
            return render(
                request,
                form_tpl,
                user=admin,
                status_code=422,
                section=resource.slug,
                action=resource.base_path,
                heading=f"Add {resource.singular}",
                values=dict(form),
                errors=exc.messages,
                **resource.form_context(db),
            )
        db.add(resource.model(**attributes))
        db.commit()
        return redirect(request, resource.base_path, notice=f"{resource.singular} saved.")

    @router.get(f"/{resource.slug}/{{record_id}}/edit")
    async def edit(
        record_id: int,
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        record = _find(db, resource, record_id)
        return render(
            request,
            form_tpl,
            user=admin,
            section=resource.slug,
            action=f"{resource.base_path}/{record_id}",
            heading=f"Edit {resource.singular}",
            values=resource.to_values(record),
            errors=[],
            **resource.form_context(db),
        )

    @router.post(f"/{resource.slug}/{{record_id}}", dependencies=[Depends(verify_csrf)])
    async def update(
        record_id: int,
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        record = _find(db, resource, record_id)
        form = await request.form()
        try:
            attributes = resource.parse(db, form, record_id)
        except ValidationError as exc:
            return render(
                request,
                form_tpl,
                user=admin,
                status_code=422,
                section=resource.slug,
                action=f"{resource.base_path}/{record_id}",
                heading=f"Edit {resource.singular}",
                values=dict(form),
                errors=exc.messages,
                **resource.form_context(db),
            )
        for key, value in attributes.items():
            setattr(record, key, value)
        db.commit()
        return redirect(
            request, resource.base_path, notice=f"{resource.singular} updated."
        )

    @router.post(
        f"/{resource.slug}/{{record_id}}/delete", dependencies=[Depends(verify_csrf)]
    )
    async def destroy(
        record_id: int,
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        record = _find(db, resource, record_id)
        if resource.guard_delete:
            try:
                resource.guard_delete(record)
            except ValidationError as exc:
                return redirect(
                    request, resource.base_path, alert=" ".join(exc.messages)
                )
        db.delete(record)
        db.commit()
        return redirect(
            request, resource.base_path, notice=f"{resource.singular} removed."
        )


register(
    AdminResource(
        slug="cars",
        singular="Car",
        model=Car,
        parse=lambda db, form, _id: validate_car_fields(form),
        to_values=lambda car: {"name": car.name, "cost_per_km": car.cost_per_km},
        listing=lambda db: list(db.scalars(select(Car).order_by(Car.name))),
        guard_delete=lambda car: assert_removable(car, "car"),
    )
)

register(
    AdminResource(
        slug="trips",
        singular="Trip",
        model=Trip,
        parse=lambda db, form, _id: validate_trip_fields(form),
        to_values=lambda trip: {"name": trip.name, "distance_km": trip.distance_km},
        listing=lambda db: list(db.scalars(select(Trip).order_by(Trip.name))),
        guard_delete=lambda trip: assert_removable(trip, "trip"),
    )
)

register(
    AdminResource(
        slug="carpool_groups",
        singular="Group",
        model=CarpoolGroup,
        parse=lambda db, form, _id: validate_carpool_group_fields(db, form),
        to_values=lambda group: {
            "name": group.name,
            "month": group.month.isoformat(),
            "car_id": group.car_id,
            "trip_id": group.trip_id,
            "series_id": group.series_id,
        },
        listing=lambda db: list(
            db.scalars(select(CarpoolGroup).order_by(CarpoolGroup.month.desc())).unique()
        ),
        form_context=lambda db: {
            "cars": list(db.scalars(select(Car).order_by(Car.name))),
            "trips": list(db.scalars(select(Trip).order_by(Trip.name))),
            # Series have no CRUD of their own — members create them implicitly.
            # This select is the escape hatch for moving a month between them.
            "series": list(
                db.scalars(select(CarpoolSeries).order_by(CarpoolSeries.name))
            ),
        },
    )
)

register(
    AdminResource(
        slug="memberships",
        singular="Member",
        model=Membership,
        parse=lambda db, form, record_id: validate_membership_fields(
            db, form, exclude_id=record_id
        ),
        to_values=lambda m: {
            "user_id": m.user_id,
            "carpool_group_id": m.carpool_group_id,
            "cost_split_percentage": m.cost_split_percentage,
        },
        listing=lambda db: sorted(
            db.scalars(select(Membership)).unique(),
            key=lambda m: (m.carpool_group.name, m.user.display_name),
        ),
        form_context=lambda db: {
            "users": list(db.scalars(select(User).order_by(User.display_name))),
            "groups": list(
                db.scalars(select(CarpoolGroup).order_by(CarpoolGroup.name)).unique()
            ),
        },
    )
)


@router.get("")
@router.get("/")
async def root(request: Request, admin: User = Depends(require_admin)):
    return redirect(request, "/admin/cars")


@router.get("/users")
async def users(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    records = list(db.scalars(select(User).order_by(User.display_name)))
    return render(
        request, "admin/users/index.html", user=admin, records=records, section="users"
    )
