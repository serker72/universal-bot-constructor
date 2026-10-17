"""create table points

Revision ID: a1b2c3d4e5f1
Revises: fdc1d76d317f
Create Date: 2026-10-17 17:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f1'
down_revision: Union[str, Sequence[str], None] = 'fdc1d76d317f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("name", sa.String(128), nullable=False, comment="Название точки"),
        sa.Column("address", sa.String(255), nullable=False, comment="Адрес точки"),
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default="Europe/Moscow",
            comment="Таймзона IANA",
        ),
        sa.Column(
            "work_interval_begin",
            sa.Time(),
            nullable=False,
            server_default="09:00:00",
            comment="Начало рабочего дня",
        ),
        sa.Column(
            "work_interval_end",
            sa.Time(),
            nullable=False,
            server_default="19:00:00",
            comment="Окончание рабочего дня",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Статус точки",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время создания",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время изменения",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_points")),
        comment="Точки продаж (филиалы)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("points")
