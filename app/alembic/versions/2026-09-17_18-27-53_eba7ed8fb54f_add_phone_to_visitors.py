"""add phone to visitors

Revision ID: eba7ed8fb54f
Revises: 09916272bfe5
Create Date: 2026-09-17 18:27:53.214965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eba7ed8fb54f'
down_revision: Union[str, Sequence[str], None] = '09916272bfe5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "visitors",
        sa.Column("phone", sa.String(32), nullable=True, comment="Номер телефона посетителя"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("visitors", "phone")
