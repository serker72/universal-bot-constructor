"""create table point_categories

Revision ID: a1b2c3d4e5f2
Revises: a1b2c3d4e5f1
Create Date: 2026-10-17 17:30:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "point_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("point_id", sa.Integer(), nullable=False, comment="ID точки"),
        sa.Column("category_id", sa.Integer(), nullable=False, comment="ID категории"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_point_categories")),
        comment="Связь многие-ко-многим: точки продаж и категории",
    )

    op.create_foreign_key(
        op.f("fk_point_categories_point_id_points"),
        "point_categories",
        "points",
        ["point_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_point_categories_category_id_categories"),
        "point_categories",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("uq_point_categories_point_id_category_id"),
        "point_categories",
        ["point_id", "category_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_point_categories_point_id"),
        "point_categories",
        ["point_id"],
    )
    op.create_index(
        op.f("ix_point_categories_category_id"),
        "point_categories",
        ["category_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("point_categories")
