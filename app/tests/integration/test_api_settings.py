"""Интеграционные тесты API системных настроек (только admin)."""

from app.services.app_settings import KEY_PAGE_SIZE, KEY_WELCOME_TEXT
from tests.integration.conftest import API


async def test_get_unauthenticated_401(client):
    resp = await client.get(f"{API}/settings")
    assert resp.status_code == 401


async def test_manager_forbidden(manager_client):
    resp = await manager_client.get(f"{API}/settings")
    assert resp.status_code == 403


async def test_get_empty_settings(admin_client):
    resp = await admin_client.get(f"{API}/settings")
    assert resp.status_code == 200
    assert resp.json() == {"settings": {}}


async def test_update_settings(admin_client):
    resp = await admin_client.put(
        f"{API}/settings",
        json={"settings": {KEY_PAGE_SIZE: "5", KEY_WELCOME_TEXT: "Привет!"}},
    )
    assert resp.status_code == 200
    assert resp.json()["settings"] == {KEY_PAGE_SIZE: "5", KEY_WELCOME_TEXT: "Привет!"}

    # прочитались обратно
    resp = await admin_client.get(f"{API}/settings")
    assert resp.json()["settings"][KEY_PAGE_SIZE] == "5"


async def test_update_partial(admin_client):
    """Частичное обновление не затирает другие ключи."""
    await admin_client.put(
        f"{API}/settings", json={"settings": {KEY_PAGE_SIZE: "7"}}
    )
    resp = await admin_client.put(
        f"{API}/settings", json={"settings": {KEY_WELCOME_TEXT: "Текст"}}
    )
    body = resp.json()["settings"]
    assert body[KEY_PAGE_SIZE] == "7"
    assert body[KEY_WELCOME_TEXT] == "Текст"


async def test_update_unknown_key_400(admin_client):
    resp = await admin_client.put(
        f"{API}/settings", json={"settings": {"bot.hack": "1"}}
    )
    assert resp.status_code == 400
    assert "bot.hack" in resp.json()["detail"]
