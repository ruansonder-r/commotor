"""Receipt PDF — a ReportLab port of the Prawn template.

ReportLab is pure Python with no system libraries behind it, which is what makes
it deployable as a Vercel function (WeasyPrint would need cairo/pango).
"""

from __future__ import annotations

import datetime as dt
import io
import re
import unicodedata

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import CarpoolGroup
from .templating import money, percent, trim


def slugify(value: str) -> str:
    """Rails' `parameterize`: 'Morning Crew' -> 'morning-crew'."""
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-") or "group"


def receipt_filename(group: CarpoolGroup) -> str:
    return f"receipt_{slugify(group.name)}_{group.month.strftime('%B_%Y')}.pdf"


def build_receipt(group: CarpoolGroup) -> bytes:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReceiptTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ReceiptBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
    )
    bold_style = ParagraphStyle(
        "ReceiptBold", parent=body_style, fontName="Helvetica-Bold"
    )

    total_trips = group.total_trips
    tally = group.monthly_tally
    generated = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M")

    story: list = [
        Paragraph(f"Carpool Receipt &mdash; {group.name}", title_style),
        Paragraph(f"Month: {group.month.strftime('%B %Y')}", body_style),
        Paragraph(
            f"Car: {group.car.name} (R{trim(group.car.cost_per_km)}/km)", body_style
        ),
        Paragraph(
            f"Route: {group.trip.name} ({trim(group.trip.distance_km)} km per trip)",
            body_style,
        ),
        Paragraph(f"Total Trips: {total_trips}", body_style),
        Paragraph(f"Total Cost: R{money(tally)}", body_style),
        Paragraph(f"Generated: {generated}", body_style),
        Spacer(1, 12),
        HRFlowable(width="100%", thickness=0.8, color=colors.black),
        Spacer(1, 12),
        Paragraph("Member Breakdown", bold_style),
        Spacer(1, 6),
    ]

    rows = [["Member", "Share", "Amount"]]
    for membership in group.memberships:
        rows.append(
            [
                membership.user.display_name,
                f"{percent(membership.cost_split_percentage)}%",
                f"R{money(membership.amount_owed)}",
            ]
        )

    table = Table(rows, colWidths=[280, 100, 120], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ]
        )
    )
    story += [
        table,
        Spacer(1, 12),
        HRFlowable(width="100%", thickness=0.8, color=colors.black),
        Spacer(1, 6),
        Paragraph(f"Total accounted: R{money(tally)}", bold_style),
    ]

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Carpool Receipt - {group.name}",
    ).build(story)
    return buffer.getvalue()
