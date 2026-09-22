"""create table request_category_fields

Revision ID: ddc4dbf735eb
Revises: 6ff1993df41c
Create Date: 2026-09-19 17:02:22.331735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddc4dbf735eb'
down_revision: Union[str, Sequence[str], None] = '6ff1993df41c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "request_category_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("category_id", sa.Integer(), nullable=False, comment="ID категории"),
        sa.Column("field_id", sa.Integer(), nullable=False, comment="ID поля из справочника request_available_fields"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0"),
                  comment="Порядок поля в диалоге заявки"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false"),
                  comment="Обязательность поля для данной категории"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False, comment="Время создания"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False, comment="Время изменения"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_category_fields")),
        comment="Привязка полей заявки к категории (состав и порядок полей диалога)",
    )

    op.create_foreign_key(
        op.f("fk_request_category_fields_category_id_categories"),
        "request_category_fields",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_request_category_fields_field_id_request_available_fields"),
        "request_category_fields",
        "request_available_fields",
        ["field_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("uq_request_category_fields_category_id_field_id"),
        "request_category_fields",
        ["category_id", "field_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_request_category_fields_category_id"),
        "request_category_fields",
        ["category_id"],
    )
    op.create_index(
        op.f("ix_request_category_fields_field_id"),
        "request_category_fields",
        ["field_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("request_category_fields")
