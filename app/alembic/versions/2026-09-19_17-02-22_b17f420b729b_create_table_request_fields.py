"""create table request_fields

Revision ID: b17f420b729b
Revises: ddc4dbf735eb
Create Date: 2026-09-19 17:02:22.645501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b17f420b729b'
down_revision: Union[str, Sequence[str], None] = 'ddc4dbf735eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "request_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("request_id", sa.Integer(), nullable=False, comment="ID заявки"),
        sa.Column("field_id", sa.Integer(), nullable=False, comment="ID поля из справочника request_available_fields"),
        sa.Column("value_text", sa.String(1024), nullable=True,
                  comment="Значение поля заявки в текстовом виде (даты ISO, время ЧЧ:ММ, числа строкой)"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False, comment="Время создания"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False, comment="Время изменения"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_fields")),
        comment="Значения динамических полей заявки",
    )

    op.create_foreign_key(
        op.f("fk_request_fields_request_id_requests"),
        "request_fields",
        "requests",
        ["request_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_request_fields_field_id_request_available_fields"),
        "request_fields",
        "request_available_fields",
        ["field_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        op.f("uq_request_fields_request_id_field_id"),
        "request_fields",
        ["request_id", "field_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_request_fields_request_id"),
        "request_fields",
        ["request_id"],
    )
    op.create_index(
        op.f("ix_request_fields_field_id"),
        "request_fields",
        ["field_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("request_fields")
