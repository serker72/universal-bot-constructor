"""create table object_managers

Revision ID: 1190b6ccb45a
Revises: ce03819dbefd
Create Date: 2026-09-02 16:20:36.000003

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1190b6ccb45a"
down_revision: Union[str, Sequence[str], None] = "ce03819dbefd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "object_managers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("object_id", sa.Integer(), nullable=False, comment="ID объекта"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="ID пользователя (менеджера)"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_object_managers")),
        comment="Связь многие-ко-многим: объекты и менеджеры",
    )

    op.create_foreign_key(
        op.f("fk_object_managers_object_id_objects"),
        "object_managers",
        "objects",
        ["object_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_object_managers_user_id_users"),
        "object_managers",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("uq_object_managers_object_id_user_id"),
        "object_managers",
        ["object_id", "user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_object_managers_object_id"),
        "object_managers",
        ["object_id"],
    )
    op.create_index(
        op.f("ix_object_managers_user_id"),
        "object_managers",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("object_managers")
