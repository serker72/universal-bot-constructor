"""Интеграционные тесты API категорий (admin-only CRUD)."""

from tests.integration.conftest import API


async def test_list_unauthenticated_401(client):
    resp = await client.get(f"{API}/categories")
    assert resp.status_code == 401


async def test_access_manager_403(manager_client):
    resp = await manager_client.get(f"{API}/categories")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin only"


async def test_create_and_get(admin_client, category_data):
    resp = await admin_client.post(f"{API}/categories", json=category_data)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == category_data["name"]
    assert body["sort_order"] == category_data["sort_order"]
    assert body["is_active"] is True
    category_id = body["id"]

    resp = await admin_client.get(f"{API}/categories/{category_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == category_data["name"]


async def test_get_missing_404(admin_client):
    resp = await admin_client.get(f"{API}/categories/9999")
    assert resp.status_code == 404


async def test_list_pagination(admin_client, category_data):
    for i in range(3):
        resp = await admin_client.post(
            f"{API}/categories",
            json={**category_data, "name": f"cat{i}", "sort_order": i},
        )
        assert resp.status_code == 201

    resp = await admin_client.get(f"{API}/categories", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


async def test_update(admin_client, category_data):
    resp = await admin_client.post(
        f"{API}/categories", json={**category_data, "name": "old"}
    )
    category_id = resp.json()["id"]

    resp = await admin_client.patch(
        f"{API}/categories/{category_id}",
        json={"name": "new", "sort_order": 5, "is_active": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "new"
    assert body["sort_order"] == 5
    assert body["is_active"] is False


async def test_update_missing_404(admin_client):
    resp = await admin_client.patch(
        f"{API}/categories/9999", json={"name": "x", "sort_order": 1}
    )
    assert resp.status_code == 404


async def test_delete(admin_client, category_data):
    resp = await admin_client.post(
        f"{API}/categories", json={**category_data, "name": "to-delete"}
    )
    category_id = resp.json()["id"]

    resp = await admin_client.delete(f"{API}/categories/{category_id}")
    assert resp.status_code == 204

    resp = await admin_client.get(f"{API}/categories/{category_id}")
    assert resp.status_code == 404


async def test_delete_missing_404(admin_client):
    resp = await admin_client.delete(f"{API}/categories/9999")
    assert resp.status_code == 404


async def test_create_validation_error(admin_client):
    # name отсутствует
    resp = await admin_client.post(f"{API}/categories", json={"sort_order": 1})
    assert resp.status_code == 422
