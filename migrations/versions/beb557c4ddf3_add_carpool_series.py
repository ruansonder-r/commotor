"""add carpool series

Revision ID: beb557c4ddf3
Revises: 2cdd43f06c6b
Create Date: 2026-10-19 14:52:51.958124

Adds the thread that ties one carpool arrangement's months together, and
backfills it so the groups that already exist keep their history: groups that
share a name, a car and a trip were the same arrangement logged month by month,
so they become one series.

The backfill also normalises `month` to the first of its month. Nothing renders
the day — every view and the receipt filename format it as `%B %Y` — so this is
unobservable, but it is a real data edit and `downgrade()` does not undo it.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'beb557c4ddf3'
down_revision = '2cdd43f06c6b'
branch_labels = None
depends_on = None

FK_NAME = "fk_carpool_groups_series_id_carpool_series"

# Spelled out as real `sa.Column`s rather than a lightweight `sa.table()`:
# without primary key metadata `inserted_primary_key` comes back empty, and
# without the `sa.Date` type the month would not round-trip as a date.
series_table = sa.Table(
    "carpool_series",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)

groups_table = sa.Table(
    "carpool_groups",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("month", sa.Date, nullable=False),
    sa.Column("car_id", sa.Integer, nullable=False),
    sa.Column("trip_id", sa.Integer, nullable=False),
    sa.Column("series_id", sa.Integer, nullable=True),
)


def _backfill() -> None:
    """Thread the existing months onto a series and snap each month to the 1st."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            groups_table.c.id,
            groups_table.c.name,
            groups_table.c.car_id,
            groups_table.c.trip_id,
            groups_table.c.month,
        ).order_by(groups_table.c.id)
    ).all()

    series_ids: dict[tuple[str, int, int], int] = {}
    for row in rows:
        key = (row.name, row.car_id, row.trip_id)
        if key not in series_ids:
            result = bind.execute(series_table.insert().values(name=row.name))
            series_ids[key] = result.inserted_primary_key[0]
        bind.execute(
            groups_table.update()
            .where(groups_table.c.id == row.id)
            .values(series_id=series_ids[key], month=row.month.replace(day=1))
        )


def upgrade() -> None:
    op.create_table(
        'carpool_series',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    # Batch mode: SQLite cannot add a foreign key in place, and the initial
    # migration already built this table through it.
    with op.batch_alter_table('carpool_groups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('series_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_carpool_groups_series_id'), ['series_id'], unique=False)
        batch_op.create_foreign_key(FK_NAME, 'carpool_series', ['series_id'], ['id'])

    _backfill()


def downgrade() -> None:
    with op.batch_alter_table('carpool_groups', schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_carpool_groups_series_id'))
        batch_op.drop_column('series_id')

    op.drop_table('carpool_series')
