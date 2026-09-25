"""add index created_at to requests

Revision ID: d2dcb2a09c5d
Revises: 4093e5d13bac
Create Date: 2026-09-24 20:50:37.491839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2dcb2a09c5d'
down_revision: Union[str, Sequence[str], None] = '4093e5d13bac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Индекс под ORDER BY created_at DESC, id DESC списка заявок без фильтра
    по статусу (индекс (status, created_at) для него не используется).
    """
    op.create_index(
        op.f("ix_requests_created_at_id"),
        "requests",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_requests_created_at_id"), table_name="requests")
