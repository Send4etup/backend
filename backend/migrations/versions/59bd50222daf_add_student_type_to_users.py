"""add_student_type_to_users

Revision ID: 59bd50222daf
Revises: b5eea8e75d57
Create Date: 2026-01-04 23:26:55.135264

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59bd50222daf'
down_revision: Union[str, None] = 'b5eea8e75d57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    """
    Добавление полей user_type и grade в таблицу users
    """
    # Добавляем поле типа пользователя
    op.add_column('users',
                  sa.Column('user_type',
                            sa.Enum('schooler', 'student', name='usertype'),
                            nullable=True,
                            comment='Тип пользователя: школьник или студент')
                  )

def downgrade():
    """
    Откат изменений
    """
    op.drop_column('users', 'user_type')

    # Удаляем enum тип (для PostgreSQL)
    op.execute('DROP TYPE IF EXISTS usertype')