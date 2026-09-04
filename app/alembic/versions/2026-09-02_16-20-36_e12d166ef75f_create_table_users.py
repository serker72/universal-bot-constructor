"""create table users

Revision ID: e12d166ef75f
Revises: 00da25ada5d6
Create Date: 2026-09-02 16:20:36.000001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.models.user import UserRole

# revision identifiers, used by Alembic.
revision: str = "e12d166ef75f"
down_revision: Union[str, Sequence[str], None] = "00da25ada5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("username", sa.String(255), nullable=False, comment="Имя пользователя (логин)"),
        sa.Column("password_hash", sa.String(255), nullable=False, comment="Хеш пароля"),
        sa.Column(
            "role",
            sa.Enum(UserRole, name="tp_user_role"),
            server_default=sa.text("'MANAGER'"),
            nullable=False,
            comment="Роль пользователя",
        ),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True, comment="Telegram ID для уведомлений"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Признак активности",
        ),
        # ----- Audit fields -----
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Время создания",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Время изменения",
        ),
        # ----- Audit fields - End -----
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        comment="Пользователи системы (администраторы и менеджеры)",
    )

    op.create_index(
        op.f("uq_users_username"),
        "users",
        ["username"],
        unique=True,
    )
    op.create_index(
        op.f("uq_users_telegram_id"),
        "users",
        ["telegram_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS tp_user_role")
