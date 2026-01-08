"""add_grade_to_users

Revision ID: b5eea8e75d57
Revises: ca4beb8efb11
Create Date: 2026-01-04 23:23:02.428888

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5eea8e75d57'
down_revision: Union[str, None] = 'ca4beb8efb11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users',
        sa.Column('grade', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'grade')
