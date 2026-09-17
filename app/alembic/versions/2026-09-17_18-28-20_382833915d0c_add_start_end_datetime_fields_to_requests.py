"""add start end datetime fields to requests

Revision ID: 382833915d0c
Revises: eba7ed8fb54f
Create Date: 2026-09-17 18:28:20.099562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '382833915d0c'
down_revision: Union[str, Sequence[str], None] = 'eba7ed8fb54f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "requests",
        sa.Column("start_date", sa.Date(), nullable=True, comment="Дата начала (из заявки)"),
    )
    op.add_column(
        "requests",
        sa.Column("start_time", sa.Time(), nullable=True, comment="Время начала (из заявки)"),
    )
    op.add_column(
        "requests",
        sa.Column("end_date", sa.Date(), nullable=True, comment="Дата окончания (из заявки)"),
    )
    op.add_column(
        "requests",
        sa.Column("end_time", sa.Time(), nullable=True, comment="Время окончания (из заявки)"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("requests", "end_time")
    op.drop_column("requests", "end_date")
    op.drop_column("requests", "start_time")
    op.drop_column("requests", "start_date")
