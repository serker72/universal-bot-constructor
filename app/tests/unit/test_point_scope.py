"""Unit-тесты условия видимости «локальное ∪ глобальное» (компиляция SQL)."""

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.domain.models import Category, Object
from app.domain.models.point_category import PointCategory
from app.domain.models.point_object import PointObject
from app.repository.point_scope import point_visible_condition


def _compile(stmt) -> str:
    return str(
        stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def test_condition_is_or_of_exists_and_not_exists():
    cond = point_visible_condition(
        Category.id,
        PointCategory,
        PointCategory.category_id,
        PointCategory.point_id,
        7,
    )
    sql = _compile(select(Category.id).where(cond))
    # «привязана к точке» OR «ни к одной точке не привязана»
    assert " OR " in sql
    assert "EXISTS" in sql
    assert "NOT (EXISTS" in sql or "NOT EXISTS" in sql
    assert "point_categories.point_id = 7" in sql
    assert "point_categories.category_id = categories.id" in sql


def test_condition_for_objects():
    cond = point_visible_condition(
        Object.id,
        PointObject,
        PointObject.object_id,
        PointObject.point_id,
        3,
    )
    sql = _compile(select(Object.id).where(cond))
    assert "point_objects.point_id = 3" in sql
    assert "point_objects.object_id = objects.id" in sql
    # глобальная часть: без условия по точке
    not_exists_part = (
        sql.split("NOT (EXISTS")[1].split(")")[0]
        if "NOT (EXISTS" in sql
        else sql.split("NOT EXISTS")[1].split(")")[0]
    )
    assert "point_id" not in not_exists_part
