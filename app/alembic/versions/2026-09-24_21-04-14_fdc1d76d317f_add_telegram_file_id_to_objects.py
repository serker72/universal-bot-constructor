"""add telegram_file_id to objects

Revision ID: fdc1d76d317f
Revises: d2dcb2a09c5d
Create Date: 2026-09-24 21:04:14.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdc1d76d317f'
down_revision: Union[str, Sequence[str], None] = 'd2dcb2a09c5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "objects",
        sa.Column(
            "telegram_file_id",
            sa.String(255),
            nullable=True,
            comment="file_id PDF в Telegram (кеш повторной отправки; сбрасывается при замене PDF)",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("objects", "telegram_file_id")
