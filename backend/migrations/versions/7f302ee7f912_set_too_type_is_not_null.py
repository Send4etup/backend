"""set too_type is not null

Revision ID: 7f302ee7f912
Revises: 2b6323bac10b
Create Date: 2025-11-17 13:01:19.374794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, String

# revision identifiers, used by Alembic.
revision: str = '7f302ee7f912'
down_revision: Union[str, None] = '2b6323bac10b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tool_type = Column(String, nullable=True, default="general")
    pass


def downgrade() -> None:
    pass
