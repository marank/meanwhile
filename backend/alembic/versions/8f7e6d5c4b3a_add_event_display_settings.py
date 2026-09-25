"""add event display settings

Revision ID: 8f7e6d5c4b3a
Revises: 2cd91f2bf870
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f7e6d5c4b3a"
down_revision: Union[str, None] = "2cd91f2bf870"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendars",
        sa.Column("force_all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "events",
        sa.Column(
            "show_recurrence_count",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("events", "show_recurrence_count")
    op.drop_column("calendars", "force_all_day")
