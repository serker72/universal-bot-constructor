"""create table settings

Revision ID: 09916272bfe5
Revises: f1e37ae3459b
Create Date: 2026-09-02 16:20:36.000008

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "09916272bfe5"
down_revision: Union[str, Sequence[str], None] = "f1e37ae3459b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "settings",
        sa.Column("key", sa.String(255), nullable=False, comment="Ключ настройки"),
        sa.Column("value", sa.Text(), nullable=False, comment="Значение настройки"),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_settings")),
        comment="Настройки системы (ключ-значение)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("settings")
