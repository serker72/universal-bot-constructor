"""Условие видимости записи для точки продаж: «локальное ∪ глобальное».

Запись доступна точке, если привязана к ней (есть строка в таблице связей
с этим point_id) ЛИБО вообще не имеет записей в таблице связей
(глобальная — общая для всех точек). Одна пара EXISTS / NOT EXISTS,
применяется и для категорий (point_categories), и для объектов
(point_objects).
"""

from sqlalchemy import ColumnExpressionArgument, exists, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from app.domain.base import Base


def point_visible_condition(
    entity_id: InstrumentedAttribute[int],
    link_model: type[Base],
    link_entity_attr: InstrumentedAttribute[int],
    link_point_attr: InstrumentedAttribute[int],
    point_id: int,
) -> ColumnExpressionArgument[bool]:
    """Запись привязана к point_id ИЛИ ни к одной точке не привязана."""
    linked_here = exists(
        select(1).where(
            link_entity_attr == entity_id,
            link_point_attr == point_id,
        )
    )
    not_linked_at_all = ~exists(
        select(1).where(link_entity_attr == entity_id)
    )
    return or_(linked_here, not_linked_at_all)
