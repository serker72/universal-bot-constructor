"""create table visitors

Revision ID: ba20061cb351
Revises: 1190b6ccb45a
Create Date: 2026-09-02 16:20:36.000004

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ba20061cb351"
down_revision: Union[str, Sequence[str], None] = "1190b6ccb45a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "visitors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, comment="Telegram ID посетителя"),
        sa.Column("full_name", sa.String(), nullable=False, comment="ФИО посетителя"),
        sa.Column(
            "consent_given",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Согласие на обработку персональных данных получено",
        ),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True, comment="Время дачи согласия"),
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Признак блокировки",
        ),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True, comment="Время блокировки"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitors")),
        comment="Посетители, зарегистрированные через бота",
    )

    op.create_index(
        op.f("uq_visitors_telegram_id"),
        "visitors",
        ["telegram_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("visitors")
