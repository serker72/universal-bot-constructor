"""create table sessions

Revision ID: f1e37ae3459b
Revises: 98ff16a9765c
Create Date: 2026-09-02 16:20:36.000007

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1e37ae3459b"
down_revision: Union[str, Sequence[str], None] = "98ff16a9765c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("device_id", sa.Integer(), nullable=False, comment="ID устройства"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="ID пользователя"),
        sa.Column("refresh_token_jti", sa.String(255), nullable=False, comment="Идентификатор refresh-токена (JTI)"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Признак активности сессии",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Время создания",
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True, comment="Время отзыва сессии"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        comment="Сессии пользователей (refresh-токены)",
    )

    op.create_foreign_key(
        op.f("fk_sessions_device_id_devices"),
        "sessions",
        "devices",
        ["device_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_sessions_user_id_users"),
        "sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("uq_sessions_refresh_token_jti"),
        "sessions",
        ["refresh_token_jti"],
        unique=True,
    )
    op.create_index(
        op.f("ix_sessions_device_id"),
        "sessions",
        ["device_id"],
    )
    op.create_index(
        op.f("ix_sessions_user_id"),
        "sessions",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("sessions")
