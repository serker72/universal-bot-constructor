"""drop request datetime comment columns

Revision ID: 8f72ad889d7c
Revises: b17f420b729b
Create Date: 2026-09-19 17:02:22.976496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f72ad889d7c'
down_revision: Union[str, Sequence[str], None] = 'b17f420b729b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Решение A (вариант 2) динамического конструктора заявок: фиксированные
    колонки дат/времени/комментария удаляются сразу, конфигурация полей
    заявки переходит в справочник request_available_fields + привязки
    request_category_fields; значения хранятся в request_fields.
    """
    op.drop_column("requests", "start_date")
    op.drop_column("requests", "start_time")
    op.drop_column("requests", "end_date")
    op.drop_column("requests", "end_time")
    op.drop_column("requests", "comment")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("requests", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("requests", sa.Column("end_time", sa.Time(), nullable=True))
    op.add_column("requests", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("requests", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("requests", sa.Column("start_date", sa.Date(), nullable=True))
