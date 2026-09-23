"""Интеграционные тесты репозиториев (реальная тестовая БД)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.models import (
    Category,
    CategoryManager,
    Object,
    ObjectManager,
    Session,
    User,
    UserRole,
)
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository
from app.repository.session import SessionRepository
from app.repository.setting import SettingRepository
from app.repository.user import UserRepository


# --- UserRepository ----------------------------------------------------------


async def test_user_add_and_get_by_username(db):
    repo = UserRepository(db)
    user = await repo.add(
        User(username="alice", password_hash="hash", role=UserRole.MANAGER)
    )
    await db.commit()

    found = await repo.get_by_username("alice")
    assert found is not None
    assert found.id == user.id
    assert found.role == UserRole.MANAGER
    assert found.is_active is True


async def test_user_get_by_username_missing(db):
    repo = UserRepository(db)
    assert await repo.get_by_username("ghost") is None


async def test_user_username_unique(db):
    repo = UserRepository(db)
    await repo.add(User(username="bob", password_hash="h", role=UserRole.ADMIN))
    await db.commit()

    # IntegrityError возникает при flush второго пользователя
    with pytest.raises(IntegrityError):
        await repo.add(User(username="bob", password_hash="h", role=UserRole.ADMIN))
        await db.commit()


async def test_user_get_by_telegram_id(db):
    repo = UserRepository(db)
    await repo.add(
        User(username="tg", password_hash="h", role=UserRole.ADMIN, telegram_id=111)
    )
    await db.commit()

    found = await repo.get_by_telegram_id(111)
    assert found is not None
    assert found.username == "tg"
    assert await repo.get_by_telegram_id(222) is None


async def test_user_list_telegram_ids_by_role(db):
    repo = UserRepository(db)
    await repo.add(
        User(username="a1", password_hash="h", role=UserRole.ADMIN, telegram_id=1)
    )
    await repo.add(
        User(username="a2", password_hash="h", role=UserRole.ADMIN, telegram_id=2)
    )
    # неактивный admin и manager не должны попасть
    await repo.add(
        User(
            username="a3",
            password_hash="h",
            role=UserRole.ADMIN,
            telegram_id=3,
            is_active=False,
        )
    )
    await repo.add(
        User(username="m1", password_hash="h", role=UserRole.MANAGER, telegram_id=4)
    )
    await db.commit()

    assert await repo.list_telegram_ids_by_role(UserRole.ADMIN) == [1, 2]
    assert await repo.list_telegram_ids_by_role(UserRole.MANAGER) == [4]


async def test_user_list_telegram_ids_by_ids(db):
    repo = UserRepository(db)
    u1 = await repo.add(
        User(username="x1", password_hash="h", role=UserRole.ADMIN, telegram_id=10)
    )
    u2 = await repo.add(
        User(
            username="x2",
            password_hash="h",
            role=UserRole.ADMIN,
            telegram_id=20,
            is_active=False,
        )
    )
    await db.commit()

    # неактивный пользователь исключается
    assert await repo.list_telegram_ids_by_ids([u1.id, u2.id]) == [10]
    assert await repo.list_telegram_ids_by_ids([]) == []


# --- CategoryRepository ------------------------------------------------------


async def test_category_crud_and_pagination(db):
    repo = CategoryRepository(db)
    for i in (3, 1, 2):
        await repo.add(Category(name=f"cat{i}", sort_order=i))
    await db.commit()

    # сортировка по sort_order
    cats = await repo.find(order_by=Category.sort_order)
    assert [c.name for c in cats] == ["cat1", "cat2", "cat3"]
    assert await repo.count() == 3

    # list_active исключает неактивные
    cats[0].is_active = False
    active = await repo.list_active()
    assert [c.name for c in active] == ["cat2", "cat3"]

    # пагинация
    page = await repo.list_active(limit=1, offset=1)
    assert [c.name for c in page] == ["cat3"]

    # удаление
    await repo.delete(cats[0])
    await db.commit()
    assert await repo.count() == 2


# --- Доступ менеджеров (объекты и категории) ---------------------------------


async def _make_manager(db, username: str) -> User:
    repo = UserRepository(db)
    user = await repo.add(
        User(username=username, password_hash="h", role=UserRole.MANAGER)
    )
    await db.flush()
    return user


async def test_manager_object_ids_direct_and_via_category(db):
    """Объекты менеджера: прямая связь ∪ объекты назначенной категории."""
    categories = CategoryRepository(db)
    objects = ObjectRepository(db)
    manager = await _make_manager(db, "m-objects")

    cat_a = await categories.add(Category(name="A", sort_order=1))
    cat_b = await categories.add(Category(name="B", sort_order=2))
    cat_c = await categories.add(Category(name="C", sort_order=3))
    await db.flush()
    obj_a = await objects.add(Object(category_id=cat_a.id, name="a1", sort_order=1))
    obj_b = await objects.add(Object(category_id=cat_b.id, name="b1", sort_order=1))
    obj_c = await objects.add(Object(category_id=cat_c.id, name="c1", sort_order=1))
    await db.flush()

    # категория A — назначена менеджеру (объект a1 доступен через неё),
    # объект b1 — прямая связь, cat_c/obj_c — чужие
    db.add(CategoryManager(category_id=cat_a.id, user_id=manager.id))
    db.add(ObjectManager(object_id=obj_b.id, user_id=manager.id))
    await db.commit()

    assert await objects.list_manager_object_ids(manager.id) == [obj_a.id, obj_b.id]
    # у другого менеджера доступ пустой
    other = await _make_manager(db, "m-none")
    await db.commit()
    assert await objects.list_manager_object_ids(other.id) == []


async def test_manager_category_ids_direct_and_via_object(db):
    """Категории менеджера: назначенные напрямую ∪ категории его объектов."""
    categories = CategoryRepository(db)
    objects = ObjectRepository(db)
    manager = await _make_manager(db, "m-categories")

    cat_a = await categories.add(Category(name="A", sort_order=1))
    cat_b = await categories.add(Category(name="B", sort_order=2))
    cat_c = await categories.add(Category(name="C", sort_order=3))
    await db.flush()
    obj_c = await objects.add(Object(category_id=cat_c.id, name="c1", sort_order=1))
    await db.flush()

    db.add(CategoryManager(category_id=cat_a.id, user_id=manager.id))
    db.add(ObjectManager(object_id=obj_c.id, user_id=manager.id))
    await db.commit()

    # cat_b не видна: ни назначения, ни объекта в ней
    assert await categories.list_manager_category_ids(manager.id) == [
        cat_a.id,
        cat_c.id,
    ]


async def test_object_access_manager_ids(db):
    """Менеджеры объекта для обработки заявок: прямые ∪ менеджеры категории."""
    categories = CategoryRepository(db)
    objects = ObjectRepository(db)
    direct = await _make_manager(db, "m-direct")
    via_category = await _make_manager(db, "m-category")
    unrelated = await _make_manager(db, "m-unrelated")

    category = await categories.add(Category(name="A", sort_order=1))
    await db.flush()
    obj = await objects.add(Object(category_id=category.id, name="a1", sort_order=1))
    await db.flush()

    db.add_all(
        [
            ObjectManager(object_id=obj.id, user_id=direct.id),
            CategoryManager(category_id=category.id, user_id=via_category.id),
        ]
    )
    await db.commit()

    assert await objects.list_access_manager_ids(obj.id) == sorted(
        [direct.id, via_category.id]
    )
    assert unrelated.id not in await objects.list_access_manager_ids(obj.id)
    # объект отсутствует
    assert await objects.list_access_manager_ids(999999) == []


# --- SettingRepository -------------------------------------------------------


async def test_setting_upsert_and_get_value(db):
    repo = SettingRepository(db)

    assert await repo.get_value("bot.page_size") is None

    await repo.upsert("bot.page_size", "5")
    await db.commit()
    assert await repo.get_value("bot.page_size") == "5"

    await repo.upsert("bot.page_size", "20")
    await db.commit()
    assert await repo.get_value("bot.page_size") == "20"
    assert await repo.count() == 1

    assert await repo.get_all() == {"bot.page_size": "20"}


# --- SessionRepository -------------------------------------------------------


async def test_session_revoke_all_for_user(db):
    user_repo = UserRepository(db)
    session_repo = SessionRepository(db)

    user = await user_repo.add(User(username="u", password_hash="h"))
    await db.flush()

    from app.domain.models import Device
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    device = Device(user_id=user.id, device_id="d1", created_at=now, last_seen_at=now)
    db.add(device)
    await db.flush()

    s1 = Session(
        device_id=device.id,
        user_id=user.id,
        refresh_token_jti="jti-1",
        is_active=True,
        created_at=now,
    )
    s2 = Session(
        device_id=device.id,
        user_id=user.id,
        refresh_token_jti="jti-2",
        is_active=True,
        created_at=now,
    )
    await session_repo.add(s1)
    await session_repo.add(s2)
    await db.commit()

    assert await session_repo.get_by_jti("jti-1") is not None

    revoked = await session_repo.revoke_all_for_user(user.id)
    await db.commit()
    assert revoked == 2

    active, active_total = await session_repo.list_by_user(user.id, only_active=True)
    assert active == []
    assert active_total == 0
    all_sessions, _total = await session_repo.list_by_user(user.id)
    assert len(all_sessions) == 2
    assert all(s.is_active is False for s in all_sessions)
