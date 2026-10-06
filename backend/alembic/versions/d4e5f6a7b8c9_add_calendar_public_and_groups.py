"""add_calendar_public_and_groups

Revision ID: d4e5f6a7b8c9
Revises: a5d9e1f3c7b2
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'a5d9e1f3c7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add public access columns to calendars table
    op.add_column('calendars', sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('calendars', sa.Column('public_role', sa.String(length=20), nullable=False, server_default='viewer'))

    # Create calendar_groups table
    op.create_table(
        'calendar_groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('calendar_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='viewer'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['calendar_id'], ['calendars.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['user_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('calendar_id', 'group_id', name='uq_calendar_group'),
    )
    op.create_index(op.f('ix_calendar_groups_calendar_id'), 'calendar_groups', ['calendar_id'], unique=False)
    op.create_index(op.f('ix_calendar_groups_group_id'), 'calendar_groups', ['group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_calendar_groups_group_id'), table_name='calendar_groups')
    op.drop_index(op.f('ix_calendar_groups_calendar_id'), table_name='calendar_groups')
    op.drop_table('calendar_groups')
    op.drop_column('calendars', 'public_role')
    op.drop_column('calendars', 'is_public')
