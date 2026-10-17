"""add point_id column to visitors

Revision ID: a1b2c3d4e5f4
Revises: a1b2c3d4e5f3
Create Date: 2026-10-17 17:30:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f4'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "visitors",
        sa.Column(
            "point_id",
            sa.Integer(),
            nullable=True,
            comment="Выбранная точка продаж (NULL — не выбрана)",
        ),
    )

    op.create_foreign_key(
        op.f("fk_visitors_point_id_points"),
        "visitors",
        "points",
        ["point_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_visitors_point_id"),
        "visitors",
        ["point_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_visitors_point_id"), table_name="visitors")
    op.drop_constraint(
        op.f("fk_visitors_point_id_points"), "visitors", type_="foreignkey"
    )
    op.drop_column("visitors", "point_id")
