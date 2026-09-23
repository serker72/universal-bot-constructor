"""add button_text to categories

Revision ID: 285f15deb694
Revises: 8f72ad889d7c
Create Date: 2026-09-23 09:58:52.118235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '285f15deb694'
down_revision: Union[str, Sequence[str], None] = '8f72ad889d7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "categories",
        sa.Column(
            "button_text",
            sa.String(64),
            nullable=True,
            comment='Текст кнопки "Создать заявку" для объектов категории (NULL — по умолчанию)',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("categories", "button_text")
