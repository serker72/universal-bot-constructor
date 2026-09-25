"""Интеграционные тесты API пользователей (admin-only)."""

import pytest
from tests.integration.conftest import API


@pytest.fixture
def new_user_data() -> dict:
    """Данные нового пользователя для создания через API."""
    return {"username": "new-manager", "password": "password-123"}


@pytest.fixture
def duplicate_username() -> str:
    """Имя пользователя, создаваемого дважды (проверка уникальности)."""
    return "dup"


async def test_create_user(admin_client, new_user_data):
    resp = await admin_client.post(f"{API}/users", json=new_user_data)
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == new_user_data["username"]
    assert body["role"] == "manager"
    assert body["is_active"] is True
    assert "password_hash" not in body


async def test_create_user_duplicate_username(admin_client, duplicate_username):
    resp = await admin_client.post(
        f"{API}/users",
        json={"username": duplicate_username, "password": "password-123"},
    )
    assert resp.status_code == 201

    resp = await admin_client.post(
        f"{API}/users",
        json={"username": duplicate_username, "password": "password-456"},
    )
    assert resp.status_code == 400


async def test_create_user_validation(admin_client):
    # короткий пароль
    resp = await admin_client.post(
        f"{API}/users", json={"username": "abc", "password": "short"}
    )
    assert resp.status_code == 422


async def test_list_users(admin_client, manager_user):
    resp = await admin_client.get(f"{API}/users")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    usernames = [u["username"] for u in body["items"]]
    assert "manager" in usernames


async def test_get_user_404(admin_client):
    resp = await admin_client.get(f"{API}/users/9999")
    assert resp.status_code == 404


async def test_update_user_password_and_role(admin_client, manager_user):
    resp = await admin_client.patch(
        f"{API}/users/{manager_user.id}",
        json={"role": "admin", "telegram_id": 777},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert body["telegram_id"] == 777


async def test_cannot_demote_last_admin(admin_client, admin_user):
    resp = await admin_client.patch(
        f"{API}/users/{admin_user.id}", json={"role": "manager"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Cannot demote the last admin"


async def test_cannot_deactivate_yourself(admin_client, admin_user):
    resp = await admin_client.patch(
        f"{API}/users/{admin_user.id}", json={"is_active": False}
    )
    assert resp.status_code == 400


async def test_cannot_delete_yourself(admin_client, admin_user):
    resp = await admin_client.delete(f"{API}/users/{admin_user.id}")
    assert resp.status_code == 400


async def test_delete_user(admin_client, manager_user):
    resp = await admin_client.delete(f"{API}/users/{manager_user.id}")
    assert resp.status_code == 204

    resp = await admin_client.get(f"{API}/users/{manager_user.id}")
    assert resp.status_code == 404


async def test_manager_forbidden_on_users(manager_client):
    resp = await manager_client.get(f"{API}/users")
    assert resp.status_code == 403

    resp = await manager_client.post(
        f"{API}/users", json={"username": "hacker", "password": "password-123"}
    )
    assert resp.status_code == 403


async def test_clear_telegram_id_with_null(admin_client, manager_user):
    """PATCH telegram_id: null — очистка (отсутствие ключа — не менять)."""
    resp = await admin_client.patch(
        f"{API}/users/{manager_user.id}", json={"telegram_id": 555}
    )
    assert resp.json()["telegram_id"] == 555
    resp = await admin_client.patch(
        f"{API}/users/{manager_user.id}", json={"is_active": True}
    )
    assert resp.json()["telegram_id"] == 555
    resp = await admin_client.patch(
        f"{API}/users/{manager_user.id}", json={"telegram_id": None}
    )
    assert resp.status_code == 200
    assert resp.json()["telegram_id"] is None


async def test_duplicate_telegram_id_400_and_rolled_back(admin_client, admin_user, manager_user):
    """Конфликт уникальности на PATCH — 400 до ответа (а не 200 с откатом)."""
    resp = await admin_client.patch(
        f"{API}/users/{admin_user.id}", json={"telegram_id": 4242}
    )
    assert resp.status_code == 200
    resp = await admin_client.patch(
        f"{API}/users/{manager_user.id}", json={"telegram_id": 4242}
    )
    assert resp.status_code == 400
    resp = await admin_client.get(f"{API}/users/{manager_user.id}")
    assert resp.json()["telegram_id"] is None


async def test_password_change_revokes_sessions(admin_client, manager_client, manager_user):
    """Смена пароля отзывает сессии: access и refresh пользователя не работают."""
    resp = await manager_client.get(f"{API}/auth/me")
    assert resp.status_code == 200
    resp = await admin_client.patch(
        f"{API}/users/{manager_user.id}", json={"password": "new-manager-pass-1"}
    )
    assert resp.status_code == 200
    resp = await manager_client.get(f"{API}/auth/me")
    assert resp.status_code == 401
    resp = await manager_client.post(f"{API}/auth/refresh")
    assert resp.status_code == 401


async def test_password_change_and_demote_admin(admin_client, admin_user, db):
    """Смена пароля + понижение admin (при другом активном admin) — без 500."""
    from app.domain.models import User, UserRole
    from app.services.password import hash_password

    other = User(
        username="admin-2", password_hash=hash_password("admin-pass-456"), role=UserRole.ADMIN
    )
    db.add(other)
    await db.commit()
    resp = await admin_client.patch(
        f"{API}/users/{other.id}",
        json={"password": "brand-new-pass-1", "role": "manager"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "manager"


async def test_demote_inactive_admin_allowed(admin_client, admin_user, db):
    """Понижение неактивного admin не упирается в «последний активный admin»."""
    from app.domain.models import User, UserRole
    from app.services.password import hash_password

    inactive = User(
        username="admin-off",
        password_hash=hash_password("admin-pass-789"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    db.add(inactive)
    await db.commit()
    resp = await admin_client.patch(
        f"{API}/users/{inactive.id}", json={"role": "manager"}
    )
    assert resp.status_code == 200


async def test_cyrillic_password_over_72_bytes_400(admin_client):
    """Кириллический пароль 40 символов (80 байт) — 400, а не 500."""
    resp = await admin_client.post(
        f"{API}/users", json={"username": "cyr-user", "password": "ж" * 40}
    )
    assert resp.status_code == 400
    assert "72" in resp.json()["detail"]


async def test_list_limit_upper_bound_422(admin_client):
    resp = await admin_client.get(f"{API}/users", params={"limit": 1000})
    assert resp.status_code == 422
