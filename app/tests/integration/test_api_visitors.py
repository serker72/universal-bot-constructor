"""Интеграционные тесты API посетителей (поиск, бан/разбан)."""

from tests.integration.conftest import API


async def test_list_unauthenticated_401(client, visitor):
    resp = await client.get(f"{API}/visitors")
    assert resp.status_code == 401


async def test_manager_forbidden(manager_client):
    resp = await manager_client.get(f"{API}/visitors")
    assert resp.status_code == 403


async def test_list_visitors(admin_client, visitor):
    resp = await admin_client.get(f"{API}/visitors")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["telegram_id"] == visitor.telegram_id
    assert item["full_name"] == visitor.full_name
    assert item["consent_given"] is True
    assert item["is_blocked"] is False


async def test_search_by_name(admin_client, visitor):
    # поиск по части ФИО
    resp = await admin_client.get(f"{API}/visitors", params={"search": "Иванов"})
    assert resp.json()["total"] == 1

    # поиск без совпадений
    resp = await admin_client.get(f"{API}/visitors", params={"search": "Петров"})
    assert resp.json()["total"] == 0


async def test_filter_blocked(admin_client, visitor):
    resp = await admin_client.get(f"{API}/visitors", params={"is_blocked": False})
    assert resp.json()["total"] == 1

    resp = await admin_client.get(f"{API}/visitors", params={"is_blocked": True})
    assert resp.json()["total"] == 0


async def test_get_visitor(admin_client, visitor):
    resp = await admin_client.get(f"{API}/visitors/{visitor.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == visitor.id


async def test_get_missing_404(admin_client):
    resp = await admin_client.get(f"{API}/visitors/9999")
    assert resp.status_code == 404


async def test_ban_unban(admin_client, visitor):
    # бан
    resp = await admin_client.post(f"{API}/visitors/{visitor.id}/ban")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_blocked"] is True
    assert body["blocked_at"] is not None

    # повторный бан — idempotent
    resp = await admin_client.post(f"{API}/visitors/{visitor.id}/ban")
    assert resp.status_code == 200

    # разбан
    resp = await admin_client.post(f"{API}/visitors/{visitor.id}/unban")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_blocked"] is False
    assert body["blocked_at"] is None


async def test_ban_missing_404(admin_client):
    resp = await admin_client.post(f"{API}/visitors/9999/ban")
    assert resp.status_code == 404
