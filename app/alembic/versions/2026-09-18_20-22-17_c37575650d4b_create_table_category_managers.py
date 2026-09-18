"""create table category_managers

Revision ID: c37575650d4b
Revises: 382833915d0c
Create Date: 2026-09-18 20:22:17.703933

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c37575650d4b'
down_revision: Union[str, Sequence[str], None] = '382833915d0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "category_managers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("category_id", sa.Integer(), nullable=False, comment="ID категории"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="ID пользователя (менеджера)"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_managers")),
        comment="Связь многие-ко-многим: категории и менеджеры",
    )

    op.create_foreign_key(
        op.f("fk_category_managers_category_id_categories"),
        "category_managers",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_category_managers_user_id_users"),
        "category_managers",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("uq_category_managers_category_id_user_id"),
        "category_managers",
        ["category_id", "user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_category_managers_category_id"),
        "category_managers",
        ["category_id"],
    )
    op.create_index(
        op.f("ix_category_managers_user_id"),
        "category_managers",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("category_managers")
