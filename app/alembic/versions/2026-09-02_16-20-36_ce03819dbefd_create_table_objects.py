"""create table objects

Revision ID: ce03819dbefd
Revises: e12d166ef75f
Create Date: 2026-09-02 16:20:36.000002

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ce03819dbefd"
down_revision: Union[str, Sequence[str], None] = "e12d166ef75f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "objects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("category_id", sa.Integer(), nullable=False, comment="ID категории"),
        sa.Column("name", sa.String(), nullable=False, comment="Наименование объекта"),
        sa.Column(
            "short_description",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
            comment="Краткое описание (HTML/Markdown)",
        ),
        sa.Column(
            "pdf_path",
            sa.String(512),
            server_default=sa.text("''"),
            nullable=False,
            comment="Путь к файлу PDF с полным описанием",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Порядок сортировки",
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_objects")),
        comment="Объекты меню бота (элементы категорий)",
    )

    op.create_foreign_key(
        op.f("fk_objects_category_id_categories"),
        "objects",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("ix_objects_category_id"),
        "objects",
        ["category_id"],
    )
    op.create_index(
        op.f("ix_objects_sort_order"),
        "objects",
        ["sort_order"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("objects")
