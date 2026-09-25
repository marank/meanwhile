"""add calendar display preferences

Revision ID: a1b2c3d4e5f6
Revises: 9a8b7c6d5e4f
Create Date: 2026-09-29 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9a8b7c6d5e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendars",
        sa.Column("first_weekday", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "calendars",
        sa.Column("show_weekends", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "calendars",
        sa.Column("today_color", sa.String(length=7), nullable=False, server_default="#eff6ff"),
    )
    op.add_column(
        "calendars",
        sa.Column("weekend_color", sa.String(length=7), nullable=False, server_default="#f9fafb"),
    )


def downgrade() -> None:
    op.drop_column("calendars", "weekend_color")
    op.drop_column("calendars", "today_color")
    op.drop_column("calendars", "show_weekends")
    op.drop_column("calendars", "first_weekday")
