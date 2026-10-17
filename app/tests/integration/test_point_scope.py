"""Интеграционные тесты фильтрации контента по точкам продаж (репозитории).

Правило видимости: запись доступна точке, если привязана к ней ЛИБО
вообще не имеет привязок (глобальная). Проверяются list/count для
категорий и объектов и проверка видимости одного объекта.
"""

from app.domain.models import Category, Object
from app.domain.models.point import Point
from app.domain.models.point_category import PointCategory
from app.domain.models.point_object import PointObject
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository


async def _make_point(db, name: str) -> Point:
    point = Point(name=name, address=f"{name}, ул. Тестовая, 1")
    db.add(point)
    await db.flush()
    return point


async def _make_category(
    repo: CategoryRepository, name: str, *, sort_order: int = 1, active: bool = True
) -> Category:
    cat = await repo.add(
        Category(name=name, sort_order=sort_order, is_active=active)
    )
    return cat


async def _link_category(db, point: Point, category: Category) -> None:
    db.add(PointCategory(point_id=point.id, category_id=category.id))
    await db.flush()


async def _make_object(
    repo: ObjectRepository,
    category: Category,
    name: str,
    *,
    sort_order: int = 1,
    active: bool = True,
) -> Object:
    return await repo.add(
        Object(
            category_id=category.id,
            name=name,
            short_description="описание",
            sort_order=sort_order,
            is_active=active,
        )
    )


async def _link_object(db, point: Point, obj: Object) -> None:
    db.add(PointObject(point_id=point.id, object_id=obj.id))
    await db.flush()


# --- категории ---------------------------------------------------------------


async def test_categories_local_and_global(db):
    """Точка видит свои категории и глобальные, но не чужие локальные."""
    categories = CategoryRepository(db)
    point_a = await _make_point(db, "A")
    point_b = await _make_point(db, "B")

    global_cat = await _make_category(categories, "global", sort_order=1)
    cat_a = await _make_category(categories, "only-a", sort_order=2)
    cat_b = await _make_category(categories, "only-b", sort_order=3)
    await _link_category(db, point_a, cat_a)
    await _link_category(db, point_b, cat_b)

    names_a = [
        c.name
        for c in await categories.list_active_for_point(point_a.id)
    ]
    assert names_a == ["global", "only-a"]
    assert await categories.count_active_for_point(point_a.id) == 2

    names_b = [
        c.name
        for c in await categories.list_active_for_point(point_b.id)
    ]
    assert names_b == ["global", "only-b"]

    # без привязок точка видит все активные — глобальные не теряются
    point_c = await _make_point(db, "C")
    names_c = [
        c.name
        for c in await categories.list_active_for_point(point_c.id)
    ]
    assert names_c == ["global"]
    assert global_cat.id is not None


async def test_categories_inactive_excluded_for_point(db):
    """Неактивные категории не видны точке (ни глобальные, ни локальные)."""
    categories = CategoryRepository(db)
    point = await _make_point(db, "A")
    await _make_category(categories, "global-off", active=False)
    local_off = await _make_category(categories, "local-off", active=False)
    await _link_category(db, point, local_off)

    assert await categories.list_active_for_point(point.id) == []
    assert await categories.count_active_for_point(point.id) == 0


# --- объекты -----------------------------------------------------------------


async def test_objects_local_and_global(db):
    """В категории точка видит свои объекты и глобальные, но не чужие."""
    categories = CategoryRepository(db)
    objects = ObjectRepository(db)
    point_a = await _make_point(db, "A")
    point_b = await _make_point(db, "B")
    category = await _make_category(categories, "cat")

    obj_global = await _make_object(objects, category, "global", sort_order=1)
    obj_a = await _make_object(objects, category, "only-a", sort_order=2)
    obj_b = await _make_object(objects, category, "only-b", sort_order=3)
    obj_off = await _make_object(
        objects, category, "off", sort_order=4, active=False
    )
    await _link_object(db, point_a, obj_a)
    await _link_object(db, point_b, obj_b)
    await _link_object(db, point_a, obj_off)  # локальный, но неактивный

    names = [
        o.name
        for o in await objects.list_by_category(
            category.id, only_active=True, point_id=point_a.id
        )
    ]
    assert names == ["global", "only-a"]

    # total пагинации считается теми же условиями
    total = await objects.count(
        *objects.active_point_conditions(category.id, point_a.id)
    )
    assert total == 2

    names_b = [
        o.name
        for o in await objects.list_by_category(
            category.id, only_active=True, point_id=point_b.id
        )
    ]
    assert names_b == ["global", "only-b"]

    # без точки — все активные (обратная совместимость)
    names_all = [
        o.name
        for o in await objects.list_by_category(category.id, only_active=True)
    ]
    assert names_all == ["global", "only-a", "only-b"]
    assert obj_off.id is not None and obj_global.id is not None


async def test_object_visible_for_point(db):
    """Проверка видимости одного объекта (открытие карточки в боте)."""
    categories = CategoryRepository(db)
    objects = ObjectRepository(db)
    point_a = await _make_point(db, "A")
    point_b = await _make_point(db, "B")
    category = await _make_category(categories, "cat")

    obj_local = await _make_object(objects, category, "only-a")
    obj_global = await _make_object(objects, category, "global")
    await _link_object(db, point_a, obj_local)

    assert await objects.is_visible_for_point(obj_local.id, point_a.id)
    assert not await objects.is_visible_for_point(obj_local.id, point_b.id)
    assert await objects.is_visible_for_point(obj_global.id, point_a.id)
    assert await objects.is_visible_for_point(obj_global.id, point_b.id)
    # объект отсутствует
    assert not await objects.is_visible_for_point(999999, point_a.id)
