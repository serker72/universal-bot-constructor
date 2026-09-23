"""cancel interval hours to minutes

Revision ID: 4093e5d13bac
Revises: 285f15deb694
Create Date: 2026-09-23 12:53:06.443525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4093e5d13bac'
down_revision: Union[str, Sequence[str], None] = '285f15deb694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Переименование ключа настройки: requests.cancel_interval_hours
    (часы) -> requests.cancel_interval_minutes (минуты), значение ×60.
    """
    op.execute(
        """
        UPDATE settings
        SET key = 'requests.cancel_interval_minutes',
            value = (value::bigint * 60)::text
        WHERE key = 'requests.cancel_interval_hours'
        """
    )


def downgrade() -> None:
    """Downgrade schema.

    Обратная конвертация: минуты -> часы (целочисленное деление на 60;
    интервалы, не кратные часу, округляются вниз).
    """
    op.execute(
        """
        UPDATE settings
        SET key = 'requests.cancel_interval_hours',
            value = (value::bigint / 60)::text
        WHERE key = 'requests.cancel_interval_minutes'
        """
    )
