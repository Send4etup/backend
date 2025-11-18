"""описание

Revision ID: 8f002be82026
Revises: 7f302ee7f912
Create Date: 2025-11-18 22:07:33.774586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f002be82026'
down_revision: Union[str, None] = '7f302ee7f912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('messages_new')
    pass


def downgrade() -> None:
    pass
