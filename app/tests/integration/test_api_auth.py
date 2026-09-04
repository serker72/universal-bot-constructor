"""Интеграционные тесты API аутентификации (/auth/*)."""

from app.services.auth import ACCESS_COOKIE, REFRESH_COOKIE
from tests.integration.conftest import API


async def test_health(client):
    resp = await client.get(f"{API}/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_login_sets_cookies_and_returns_user(
    client, admin_user, admin_credentials, device_id
):
    resp = await client.post(
        f"{API}/auth/login",
        json={**admin_credentials, "device_id": device_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == admin_credentials["username"]
    assert body["role"] == "admin"
    assert "password_hash" not in body

    cookies = resp.headers.get_list("set-cookie")
    assert any(c.startswith(f"{ACCESS_COOKIE}=") for c in cookies)
    assert any(c.startswith(f"{REFRESH_COOKIE}=") for c in cookies)
    assert any("httponly" in c.lower() for c in cookies)


async def test_login_wrong_password_401(client, admin_user, admin_credentials):
    resp = await client.post(
        f"{API}/auth/login",
        json={
            "username": admin_credentials["username"],
            "password": "wrong-password",
            "device_id": "device-login-001",
        },
    )
    assert resp.status_code == 401


async def test_login_validation_error(client):
    # device_id короче 8 символов
    resp = await client.post(
        f"{API}/auth/login",
        json={"username": "admin", "password": "x", "device_id": "short"},
    )
    assert resp.status_code == 422


async def test_access_without_token_401(client):
    resp = await client.get(f"{API}/users")
    assert resp.status_code == 401


async def test_access_with_garbage_token_401(client):
    client.cookies.set(ACCESS_COOKIE, "garbage.token.value")
    resp = await client.get(f"{API}/users")
    assert resp.status_code == 401


async def test_me_flow_login_refresh_logout(
    client, admin_user, admin_credentials, device_id
):
    """Полный цикл: login -> доступ -> refresh -> logout -> доступ запрещён."""
    resp = await client.post(
        f"{API}/auth/login",
        json={**admin_credentials, "device_id": device_id},
    )
    assert resp.status_code == 200

    # доступ с access-токеном
    resp = await client.get(f"{API}/users")
    assert resp.status_code == 200

    # refresh: старый refresh больше не работает (ротация)
    old_refresh = client.cookies.get(REFRESH_COOKIE)
    resp = await client.post(f"{API}/auth/refresh")
    assert resp.status_code == 200
    new_refresh = client.cookies.get(REFRESH_COOKIE)
    assert new_refresh != old_refresh

    # старый refresh-токен отозван (blacklist + ротация)
    client.cookies.set(REFRESH_COOKIE, old_refresh)
    resp = await client.post(f"{API}/auth/refresh")
    assert resp.status_code == 401

    # возвращаем рабочие cookies
    client.cookies.set(REFRESH_COOKIE, new_refresh)

    # logout
    resp = await client.post(f"{API}/auth/logout")
    assert resp.status_code == 200

    # после logout access-токен в blacklist
    resp = await client.get(f"{API}/users")
    assert resp.status_code == 401


async def test_refresh_without_token_401(client):
    resp = await client.post(f"{API}/auth/refresh")
    assert resp.status_code == 401
