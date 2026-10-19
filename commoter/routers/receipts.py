"""Month-end receipt, rendered server-side as a PDF."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..pdf import build_receipt, receipt_filename
from ..security import require_user
from .carpool_groups import load_group_for_user

router = APIRouter()


@router.get("/carpool_groups/{group_id}/receipt")
async def show(
    group_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    group = load_group_for_user(db, user, group_id)
    return Response(
        content=build_receipt(group),
        media_type="application/pdf",
        headers={
            # `attachment` so mobile browsers hand it to the OS share/save sheet,
            # which is what the native PDF bridge used to do.
            "Content-Disposition": f'attachment; filename="{receipt_filename(group)}"'
        },
    )
