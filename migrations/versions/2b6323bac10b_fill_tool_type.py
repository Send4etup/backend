"""fill tool_type

Revision ID: 2b6323bac10b
Revises: 59a08c81f26f
Create Date: 2025-11-17 13:00:22.467021

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b6323bac10b'
down_revision: Union[str, None] = '59a08c81f26f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE messages SET tool_type='general'")
    pass


def downgrade() -> None:
    pass
