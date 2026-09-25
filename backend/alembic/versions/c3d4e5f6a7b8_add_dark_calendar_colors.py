"""add dark calendar colors

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-29 00:00:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calendars", sa.Column("dark_color", sa.String(length=7), nullable=False, server_default="#60a5fa"))
    op.add_column("calendars", sa.Column("dark_today_color", sa.String(length=7), nullable=False, server_default="#27272a"))
    op.add_column("calendars", sa.Column("dark_weekend_color", sa.String(length=7), nullable=False, server_default="#18181b"))


def downgrade() -> None:
    op.drop_column("calendars", "dark_weekend_color")
    op.drop_column("calendars", "dark_today_color")
    op.drop_column("calendars", "dark_color")
