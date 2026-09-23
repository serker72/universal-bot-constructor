"""Интеграционные тесты API категорий.

CRUD — только admin; менеджер читает доступные категории (назначенные
напрямую ∪ категории своих объектов).
"""

from tests.integration.conftest import API


async def test_list_unauthenticated_401(client):
    resp = await client.get(f"{API}/categories")
    assert resp.status_code == 401


async def test_manager_sees_nothing_without_assignment(manager_client, category):
    """Без назначений менеджер не видит ни списка, ни категории по id."""
    resp = await manager_client.get(f"{API}/categories")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = await manager_client.get(f"{API}/categories/{category.id}")
    assert resp.status_code == 404


async def test_manager_sees_assigned_category(
    admin_client, manager_client, manager_user, category
):
    """Прямое назначение категории -> категория видна менеджеру."""
    resp = await admin_client.put(
        f"{API}/categories/{category.id}/managers",
        json={"user_ids": [manager_user.id]},
    )
    assert resp.status_code == 200

    resp = await manager_client.get(f"{API}/categories")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [c["id"] for c in body["items"]] == [category.id]

    resp = await manager_client.get(f"{API}/categories/{category.id}")
    assert resp.status_code == 200


async def test_manager_sees_category_of_own_object(
    admin_client, manager_client, manager_user, category, obj
):
    """Категория объекта с прямой связью объект↔менеджер — доступна."""
    resp = await admin_client.put(
        f"{API}/objects/{obj.id}/managers",
        json={"user_ids": [manager_user.id]},
    )
    assert resp.status_code == 200

    resp = await manager_client.get(f"{API}/categories")
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()["items"]] == [category.id]


async def test_write_manager_403(manager_client, category_data):
    """Создание категории — только admin (чтение менеджеру доступно, запись нет)."""
    resp = await manager_client.post(f"{API}/categories", json=category_data)
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


async def test_button_text_flow(admin_client, category_data):
    """button_text: создание, изменение, сброс пустой строкой, null = не менять."""
    # создание без button_text → None (текст по умолчанию в боте)
    resp = await admin_client.post(f"{API}/categories", json=category_data)
    category_id = resp.json()["id"]
    assert resp.json()["button_text"] is None

    # установка своего текста
    resp = await admin_client.patch(
        f"{API}/categories/{category_id}", json={"button_text": "Заказать столик"}
    )
    assert resp.status_code == 200
    assert resp.json()["button_text"] == "Заказать столик"

    # null — поле не меняется
    resp = await admin_client.patch(
        f"{API}/categories/{category_id}", json={"name": "new-name"}
    )
    assert resp.json()["button_text"] == "Заказать столик"

    # "" — сброс на дефолт
    resp = await admin_client.patch(
        f"{API}/categories/{category_id}", json={"button_text": ""}
    )
    assert resp.json()["button_text"] is None


async def test_button_text_create(admin_client, category_data):
    resp = await admin_client.post(
        f"{API}/categories", json={**category_data, "button_text": "Забронировать"}
    )
    assert resp.status_code == 201
    assert resp.json()["button_text"] == "Забронировать"


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
