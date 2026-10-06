"""add event participants

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_participants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "email", name="uq_event_participant_email"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_participant_user"),
    )
    op.create_index(op.f("ix_event_participants_event_id"), "event_participants", ["event_id"], unique=False)
    op.create_index(op.f("ix_event_participants_user_id"), "event_participants", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_participants_user_id"), table_name="event_participants")
    op.drop_index(op.f("ix_event_participants_event_id"), table_name="event_participants")
    op.drop_table("event_participants")
