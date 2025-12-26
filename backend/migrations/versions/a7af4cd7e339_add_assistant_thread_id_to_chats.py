"""add_assistant_thread_id_to_chats

Revision ID: a7af4cd7e339
Revises: 8f002be82026
Create Date: 2025-12-19 19:43:36.055323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7af4cd7e339'
down_revision: Union[str, None] = '8f002be82026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chats',
        sa.Column('assistant_thread_id', sa.String(), nullable=True, default=None)
    )


def downgrade() -> None:
    op.drop_column('chats', 'assistant_thread_id')
