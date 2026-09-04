"""Интеграционные тесты API сессий (список, отзыв одной/всех)."""

from tests.integration.conftest import API


async def test_list_unauthenticated_401(client):
    resp = await client.get(f"{API}/sessions")
    assert resp.status_code == 401


async def test_manager_forbidden(manager_client):
    resp = await manager_client.get(f"{API}/sessions")
    assert resp.status_code == 403


async def test_list_after_login(admin_client, admin_user):
    """После login у admin одна активная сессия."""
    resp = await admin_client.get(f"{API}/sessions", params={"only_active": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    session = body["items"][0]
    assert session["user_id"] == admin_user.id
    assert session["is_active"] is True
    return session["id"]


async def test_filter_by_user(admin_client, admin_user, manager_client, manager_user):
    resp = await admin_client.get(f"{API}/sessions", params={"user_id": manager_user.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["user_id"] == manager_user.id


async def test_revoke_session(
    admin_client, manager_client, manager_user, admin_user
):
    """Отзыв сессии менеджера: сессия неактивна, его refresh перестаёт работать."""
    from app.services.auth import REFRESH_COOKIE

    # найти сессию менеджера
    resp = await admin_client.get(
        f"{API}/sessions", params={"user_id": manager_user.id, "only_active": True}
    )
    session_id = resp.json()["items"][0]["id"]

    # отозвать
    resp = await admin_client.post(f"{API}/sessions/{session_id}/revoke")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # повторный отзыв — idempotent (уже неактивна, ошибок нет)
    resp = await admin_client.post(f"{API}/sessions/{session_id}/revoke")
    assert resp.status_code == 200

    # refresh менеджера больше не работает
    resp = await manager_client.post(f"{API}/auth/refresh")
    assert resp.status_code == 401


async def test_revoke_missing_404(admin_client):
    resp = await admin_client.post(f"{API}/sessions/9999/revoke")
    assert resp.status_code == 404


async def test_revoke_all_for_user(
    admin_client, manager_client, manager_user, admin_user
):
    resp = await admin_client.post(f"{API}/sessions/users/{manager_user.id}/revoke-all")
    assert resp.status_code == 200
    assert resp.json() == {"revoked": 1}

    # после revoke-all refresh менеджера не работает
    resp = await manager_client.post(f"{API}/auth/refresh")
    assert resp.status_code == 401

    # пользователь без сессий — 0
    resp = await admin_client.post(f"{API}/sessions/users/9999/revoke-all")
    assert resp.json() == {"revoked": 0}
