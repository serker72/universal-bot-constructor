"""create table devices

Revision ID: 98ff16a9765c
Revises: d0df3d53a863
Create Date: 2026-09-02 16:20:36.000006

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98ff16a9765c"
down_revision: Union[str, Sequence[str], None] = "d0df3d53a863"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="ID пользователя"),
        sa.Column("device_id", sa.String(255), nullable=False, comment="Идентификатор устройства (thumbmarkjs)"),
        sa.Column("user_agent", sa.String(512), nullable=True, comment="User-Agent браузера"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Время создания",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Время последней активности",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        comment="Устройства, с которых пользователи входят во frontend",
    )

    op.create_foreign_key(
        op.f("fk_devices_user_id_users"),
        "devices",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("ix_devices_user_id"),
        "devices",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("devices")
