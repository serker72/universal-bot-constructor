"""Интеграционные тесты API точек продаж (филиалов).

CRUD и привязки — только admin. Валидация таймзоны и графика работы — 400
(бизнес-правила), некорректный JSON — 422 (pydantic).
"""

from tests.integration.conftest import API


async def test_list_unauthenticated_401(client):
    resp = await client.get(f"{API}/points")
    assert resp.status_code == 401


async def test_write_manager_403(manager_client, point_data):
    """Точки заводит только admin."""
    resp = await manager_client.post(f"{API}/points", json=point_data)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin only"

    resp = await manager_client.get(f"{API}/points")
    assert resp.status_code == 403


async def test_create_and_get(admin_client, point_data):
    resp = await admin_client.post(f"{API}/points", json=point_data)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == point_data["name"]
    assert body["address"] == point_data["address"]
    assert body["timezone"] == "Europe/Moscow"
    # график по умолчанию 09:00–19:00
    assert body["work_interval_begin"] == "09:00:00"
    assert body["work_interval_end"] == "19:00:00"
    assert body["is_active"] is True

    resp = await admin_client.get(f"{API}/points/{body['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == point_data["name"]


async def test_create_bad_timezone_400(admin_client, point_data):
    resp = await admin_client.post(
        f"{API}/points", json={**point_data, "timezone": "Mars/Olympus"}
    )
    assert resp.status_code == 400
    assert "таймзона" in resp.json()["detail"].lower()


async def test_create_bad_interval_400(admin_client, point_data):
    """begin >= end — невалидный график."""
    resp = await admin_client.post(
        f"{API}/points",
        json={
            **point_data,
            "work_interval_begin": "19:00",
            "work_interval_end": "09:00",
        },
    )
    assert resp.status_code == 400

    # равные границы — тоже невалидно
    resp = await admin_client.post(
        f"{API}/points",
        json={
            **point_data,
            "work_interval_begin": "10:00",
            "work_interval_end": "10:00",
        },
    )
    assert resp.status_code == 400


async def test_create_validation_error_422(admin_client):
    # name отсутствует
    resp = await admin_client.post(f"{API}/points", json={"address": "a"})
    assert resp.status_code == 422


async def test_update_patch_semantics(admin_client, point_data):
    resp = await admin_client.post(f"{API}/points", json=point_data)
    point_id = resp.json()["id"]

    # только переданные поля меняются
    resp = await admin_client.patch(
        f"{API}/points/{point_id}", json={"name": "Новое имя"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Новое имя"
    assert body["address"] == point_data["address"]
    assert body["timezone"] == "Europe/Moscow"


async def test_update_bad_timezone_400(admin_client, point_data):
    resp = await admin_client.post(f"{API}/points", json=point_data)
    point_id = resp.json()["id"]

    resp = await admin_client.patch(
        f"{API}/points/{point_id}", json={"timezone": "Nowhere/Land"}
    )
    assert resp.status_code == 400


async def test_update_interval_half_change(admin_client, point_data):
    """График проверяется по объединённым значениям: можно менять одну границу."""
    resp = await admin_client.post(f"{API}/points", json=point_data)
    point_id = resp.json()["id"]

    # 09:00 (существующее) < 21:00 — валидно
    resp = await admin_client.patch(
        f"{API}/points/{point_id}", json={"work_interval_end": "21:00"}
    )
    assert resp.status_code == 200
    assert resp.json()["work_interval_end"] == "21:00:00"

    # 22:00 (новое начало) >= 21:00 — невалидно
    resp = await admin_client.patch(
        f"{API}/points/{point_id}", json={"work_interval_begin": "22:00"}
    )
    assert resp.status_code == 400


async def test_update_missing_404(admin_client):
    resp = await admin_client.patch(f"{API}/points/9999", json={"name": "x"})
    assert resp.status_code == 404


async def test_list_pagination(admin_client, point_data):
    for i in range(3):
        resp = await admin_client.post(
            f"{API}/points", json={**point_data, "name": f"point{i}"}
        )
        assert resp.status_code == 201

    resp = await admin_client.get(f"{API}/points", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_delete(admin_client, point_data):
    resp = await admin_client.post(f"{API}/points", json=point_data)
    point_id = resp.json()["id"]

    resp = await admin_client.delete(f"{API}/points/{point_id}")
    assert resp.status_code == 204

    resp = await admin_client.get(f"{API}/points/{point_id}")
    assert resp.status_code == 404


async def test_delete_missing_404(admin_client):
    resp = await admin_client.delete(f"{API}/points/9999")
    assert resp.status_code == 404


# -- привязки категорий/объектов ------------------------------------------------


async def test_categories_empty_by_default(admin_client, point_a):
    """Нет привязок — точка работает со всеми глобальными категориями."""
    resp = await admin_client.get(f"{API}/points/{point_a.id}/categories")
    assert resp.status_code == 200
    assert resp.json() == {"point_id": point_a.id, "category_ids": []}


async def test_set_categories_diff(admin_client, point_a, category, category_global):
    """PUT — diff-замена: добавление, повторный PUT без id убирает привязку."""
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/categories",
        json={"category_ids": [category.id, category_global.id]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["category_ids"] == sorted([category.id, category_global.id])

    resp = await admin_client.get(f"{API}/points/{point_a.id}/categories")
    assert resp.json()["category_ids"] == sorted([category.id, category_global.id])

    # оставляем только одну — вторая отвязывается
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/categories",
        json={"category_ids": [category_global.id]},
    )
    assert resp.json()["category_ids"] == [category_global.id]

    # пустой список — снять все привязки (точка снова видит всё глобальное)
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/categories", json={"category_ids": []}
    )
    assert resp.json()["category_ids"] == []


async def test_set_categories_unknown_id_400(admin_client, point_a):
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/categories", json={"category_ids": [9999]}
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"]


async def test_categories_point_missing_404(admin_client, category):
    resp = await admin_client.get(f"{API}/points/9999/categories")
    assert resp.status_code == 404

    resp = await admin_client.put(
        f"{API}/points/9999/categories", json={"category_ids": [category.id]}
    )
    assert resp.status_code == 404


async def test_set_objects_diff(admin_client, point_a, obj, object_of_point_a):
    """PUT — diff-замена набора объектов точки (object_of_point_a уже привязан)."""
    # фикстура привязала object_of_point_a; заменяем набор на [obj]
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/objects",
        json={"object_ids": [obj.id]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["object_ids"] == [obj.id]

    resp = await admin_client.get(f"{API}/points/{point_a.id}/objects")
    assert resp.json()["object_ids"] == [obj.id]

    # добавление второго объекта
    both = sorted([obj.id, object_of_point_a.id])
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/objects",
        json={"object_ids": both},
    )
    assert resp.json()["object_ids"] == both

    # пустой список — снять все привязки
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/objects", json={"object_ids": []}
    )
    assert resp.json()["object_ids"] == []


async def test_set_objects_unknown_id_400(admin_client, point_a):
    resp = await admin_client.put(
        f"{API}/points/{point_a.id}/objects", json={"object_ids": [9999]}
    )
    assert resp.status_code == 400


async def test_bindings_manager_403(manager_client, point_a, category):
    resp = await manager_client.get(f"{API}/points/{point_a.id}/categories")
    assert resp.status_code == 403

    resp = await manager_client.put(
        f"{API}/points/{point_a.id}/categories", json={"category_ids": [category.id]}
    )
    assert resp.status_code == 403


# -- каскады --------------------------------------------------------------------


async def test_delete_point_removes_links(admin_client, point_a, category, obj):
    """Удаление точки снимает связи, но не сами категории/объекты."""
    await admin_client.put(
        f"{API}/points/{point_a.id}/categories", json={"category_ids": [category.id]}
    )
    await admin_client.put(
        f"{API}/points/{point_a.id}/objects", json={"object_ids": [obj.id]}
    )

    resp = await admin_client.delete(f"{API}/points/{point_a.id}")
    assert resp.status_code == 204

    # категория и объект живы, привязок нет
    assert (await admin_client.get(f"{API}/categories/{category.id}")).status_code == 200
    assert (await admin_client.get(f"{API}/objects/{obj.id}")).status_code == 200


async def test_delete_category_removes_point_link(admin_client, point_a, category):
    """Удаление категории каскадно убирает связь с точкой."""
    await admin_client.put(
        f"{API}/points/{point_a.id}/categories", json={"category_ids": [category.id]}
    )

    resp = await admin_client.delete(f"{API}/categories/{category.id}")
    assert resp.status_code == 204

    resp = await admin_client.get(f"{API}/points/{point_a.id}/categories")
    assert resp.json()["category_ids"] == []


# -- отметка is_global в списках ------------------------------------------------


async def test_categories_is_global_flag(
    admin_client, point_a, category, category_global
):
    """Категория без привязок — глобальная; привязанная — локальная."""
    await admin_client.put(
        f"{API}/points/{point_a.id}/categories", json={"category_ids": [category.id]}
    )

    resp = await admin_client.get(f"{API}/categories")
    assert resp.status_code == 200
    by_id = {c["id"]: c for c in resp.json()["items"]}
    assert by_id[category_global.id]["is_global"] is True
    assert by_id[category.id]["is_global"] is False


async def test_objects_is_global_flag(
    admin_client, point_a, obj, object_of_point_a
):
    """object_of_point_a привязан к точке A — не глобальный; obj — глобальный."""
    resp = await admin_client.get(f"{API}/objects")
    assert resp.status_code == 200
    by_id = {o["id"]: o for o in resp.json()["items"]}
    assert by_id[obj.id]["is_global"] is True
    assert by_id[object_of_point_a.id]["is_global"] is False
