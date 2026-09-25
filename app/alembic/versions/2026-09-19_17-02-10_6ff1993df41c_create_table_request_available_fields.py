"""create table request_available_fields

Revision ID: 6ff1993df41c
Revises: c37575650d4b
Create Date: 2026-09-19 17:02:10.591485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

import enum


# Замороженная копия enum на момент миграции: изменения app.domain.models
# не должны менять историю схемы
class RequestFieldType(str, enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    TIME = "time"
    SELECT = "select"


# revision identifiers, used by Alembic.
revision: str = '6ff1993df41c'
down_revision: Union[str, Sequence[str], None] = 'c37575650d4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "request_available_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("code", sa.String(64), nullable=False, comment="Уникальный технический код поля (например delivery_time)"),
        sa.Column(
            "type",
            sa.Enum(
                RequestFieldType,
                name=op.f("tp_request_field_type"),
                # хранить значения enum ("text"), а не имена ("TEXT")
                values_callable=lambda e: [m.value for m in e],
            ),
            nullable=False,
            comment="Тип поля (text/number/date/time/select)",
        ),
        sa.Column("label", sa.String(255), nullable=False, comment="Подпись поля для пользователя"),
        sa.Column("is_required_default", sa.Boolean(), nullable=False, server_default=sa.text("false"),
                  comment="Обязательность поля по умолчанию при привязке к категории"),
        sa.Column("meta_data", JSONB(), nullable=True,
                  comment="Параметры поля: опции SELECT, шаг минут TIME, min/max NUMBER, max_length TEXT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False, comment="Время создания"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False, comment="Время изменения"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_available_fields")),
        comment="Справочник доступных полей заявки (динамический конструктор заявки)",
    )

    op.create_index(
        op.f("uq_request_available_fields_code"),
        "request_available_fields",
        ["code"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("request_available_fields")
    op.execute("DROP TYPE IF EXISTS tp_request_field_type")
