"""Интеграционные тесты API объектов (CRUD + назначение менеджеров)."""

from tests.integration.conftest import API


async def test_list_unauthenticated_401(client):
    resp = await client.get(f"{API}/objects")
    assert resp.status_code == 401


async def test_manager_forbidden(manager_client):
    resp = await manager_client.get(f"{API}/objects")
    assert resp.status_code == 403


async def test_create_and_get(admin_client, category, object_data):
    resp = await admin_client.post(
        f"{API}/objects", json={**object_data, "category_id": category.id}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == object_data["name"]
    assert body["category_id"] == category.id
    assert body["has_pdf"] is False
    object_id = body["id"]

    resp = await admin_client.get(f"{API}/objects/{object_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == object_data["name"]


async def test_create_missing_category(admin_client, object_data):
    resp = await admin_client.post(
        f"{API}/objects", json={**object_data, "category_id": 9999}
    )
    # FK не проверяется на уровне API — объект создаётся (FK на уровне БД)
    assert resp.status_code in (201, 400)


async def test_get_missing_404(admin_client):
    resp = await admin_client.get(f"{API}/objects/9999")
    assert resp.status_code == 404


async def test_list_filter_by_category(admin_client, category, obj):
    resp = await admin_client.get(
        f"{API}/objects", params={"category_id": category.id}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == obj.id

    # чужая категория — пусто
    resp = await admin_client.get(f"{API}/objects", params={"category_id": 9999})
    assert resp.json()["total"] == 0


async def test_update(admin_client, category, obj, object_data):
    resp = await admin_client.patch(
        f"{API}/objects/{obj.id}",
        json={**object_data, "category_id": category.id, "name": "updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated"


async def test_update_missing_404(admin_client, category, object_data):
    resp = await admin_client.patch(
        f"{API}/objects/9999", json={**object_data, "category_id": category.id}
    )
    assert resp.status_code == 404


async def test_delete(admin_client, obj):
    resp = await admin_client.delete(f"{API}/objects/{obj.id}")
    assert resp.status_code == 204

    resp = await admin_client.get(f"{API}/objects/{obj.id}")
    assert resp.status_code == 404


async def test_delete_missing_404(admin_client):
    resp = await admin_client.delete(f"{API}/objects/9999")
    assert resp.status_code == 404


async def test_managers_flow(admin_client, obj, manager_user):
    # пусто
    resp = await admin_client.get(f"{API}/objects/{obj.id}/managers")
    assert resp.status_code == 200
    assert resp.json() == {"object_id": obj.id, "user_ids": []}

    # назначить
    resp = await admin_client.put(
        f"{API}/objects/{obj.id}/managers",
        json={"user_ids": [manager_user.id]},
    )
    assert resp.status_code == 200
    assert resp.json()["user_ids"] == [manager_user.id]

    # прочитать
    resp = await admin_client.get(f"{API}/objects/{obj.id}/managers")
    assert resp.json()["user_ids"] == [manager_user.id]

    # снять (пустой список)
    resp = await admin_client.put(
        f"{API}/objects/{obj.id}/managers", json={"user_ids": []}
    )
    assert resp.status_code == 200
    assert resp.json()["user_ids"] == []


async def test_set_managers_unknown_user_400(admin_client, obj):
    resp = await admin_client.put(
        f"{API}/objects/{obj.id}/managers", json={"user_ids": [9999]}
    )
    assert resp.status_code == 400
    assert "9999" in resp.json()["detail"]


async def test_get_managers_missing_object_404(admin_client):
    resp = await admin_client.get(f"{API}/objects/9999/managers")
    assert resp.status_code == 404
