"""add event categories

Revision ID: 9a8b7c6d5e4f
Revises: 8f7e6d5c4b3a
Create Date: 2026-09-29 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a8b7c6d5e4f"
down_revision: Union[str, None] = "8f7e6d5c4b3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("calendar_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["calendar_id"], ["calendars.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("calendar_id", "name", name="uq_category_calendar_name"),
    )
    op.create_index(op.f("ix_categories_calendar_id"), "categories", ["calendar_id"])
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.String(length=36), nullable=True))
        batch_op.create_index(op.f("ix_events_category_id"), ["category_id"])
        batch_op.create_foreign_key(
            "fk_events_category_id_categories",
            "categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("fk_events_category_id_categories", type_="foreignkey")
        batch_op.drop_index(op.f("ix_events_category_id"))
        batch_op.drop_column("category_id")
    op.drop_index(op.f("ix_categories_calendar_id"), table_name="categories")
    op.drop_table("categories")
