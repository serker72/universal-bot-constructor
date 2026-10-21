"""add_multiselect_boolean_field_types

Revision ID: f81df234f832
Revises: a1b2c3d4e5f4
Create Date: 2026-10-21 14:28:13.324261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f81df234f832'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавить значения multiselect и boolean в enum tp_request_field_type
    op.execute(
        "ALTER TYPE tp_request_field_type "
        "ADD VALUE IF NOT EXISTS 'multiselect'"
    )
    op.execute(
        "ALTER TYPE tp_request_field_type "
        "ADD VALUE IF NOT EXISTS 'boolean'"
    )


def downgrade() -> None:
    # Удалить enum-значения невозможно напрямую —
    # пересоздать тип с прежним набором значений
    op.execute(
        "ALTER TYPE tp_request_field_type RENAME TO tp_request_field_type_old"
    )
    op.execute(
        "CREATE TYPE tp_request_field_type AS ENUM "
        "('text','number','date','time','select')"
    )
    op.execute(
        "ALTER TABLE request_available_fields "
        "ALTER COLUMN type TYPE tp_request_field_type "
        "USING (CASE type::text "
        "WHEN 'multiselect' THEN 'select' "
        "WHEN 'boolean' THEN 'text' "
        "ELSE type::text END)::tp_request_field_type"
    )
    op.execute("DROP TYPE tp_request_field_type_old")
