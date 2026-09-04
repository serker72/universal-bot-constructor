"""Интеграционные тесты репозиториев (реальная тестовая БД)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.models import Category, Session, User, UserRole
from app.repository.category import CategoryRepository
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

    active = await session_repo.list_by_user(user.id, only_active=True)
    assert active == []
    all_sessions = await session_repo.list_by_user(user.id)
    assert len(all_sessions) == 2
    assert all(s.is_active is False for s in all_sessions)
