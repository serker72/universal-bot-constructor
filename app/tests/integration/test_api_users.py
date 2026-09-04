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
