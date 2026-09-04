"""create table requests

Revision ID: d0df3d53a863
Revises: ba20061cb351
Create Date: 2026-09-02 16:20:36.000005

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.models.request import RequestStatus

# revision identifiers, used by Alembic.
revision: str = "d0df3d53a863"
down_revision: Union[str, Sequence[str], None] = "ba20061cb351"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("visitor_id", sa.Integer(), nullable=False, comment="ID посетителя"),
        sa.Column("object_id", sa.Integer(), nullable=False, comment="ID объекта"),
        sa.Column("phone", sa.String(32), nullable=False, comment="Номер телефона"),
        sa.Column("comment", sa.Text(), nullable=True, comment="Комментарий посетителя"),
        sa.Column(
            "status",
            sa.Enum(RequestStatus, name="tp_request_status"),
            server_default=sa.text(f"'{RequestStatus.NEW.name}'"),
            nullable=False,
            comment="Статус заявки",
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Время подтверждения заявки",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requests")),
        comment="Заявки посетителей на объекты",
    )

    op.create_foreign_key(
        op.f("fk_requests_visitor_id_visitors"),
        "requests",
        "visitors",
        ["visitor_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_requests_object_id_objects"),
        "requests",
        "objects",
        ["object_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        op.f("ix_requests_visitor_id"),
        "requests",
        ["visitor_id"],
    )
    op.create_index(
        op.f("ix_requests_object_id"),
        "requests",
        ["object_id"],
    )
    op.create_index(
        op.f("ix_requests_status_created_at"),
        "requests",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("requests")
    op.execute("DROP TYPE IF EXISTS tp_request_status")
