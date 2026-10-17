"""create table point_objects

Revision ID: a1b2c3d4e5f3
Revises: a1b2c3d4e5f2
Create Date: 2026-10-17 17:30:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f3'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "point_objects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("point_id", sa.Integer(), nullable=False, comment="ID точки"),
        sa.Column("object_id", sa.Integer(), nullable=False, comment="ID объекта"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_point_objects")),
        comment="Связь многие-ко-многим: точки продаж и объекты",
    )

    op.create_foreign_key(
        op.f("fk_point_objects_point_id_points"),
        "point_objects",
        "points",
        ["point_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_point_objects_object_id_objects"),
        "point_objects",
        "objects",
        ["object_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("uq_point_objects_point_id_object_id"),
        "point_objects",
        ["point_id", "object_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_point_objects_point_id"),
        "point_objects",
        ["point_id"],
    )
    op.create_index(
        op.f("ix_point_objects_object_id"),
        "point_objects",
        ["object_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("point_objects")
