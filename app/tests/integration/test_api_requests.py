"""Интеграционные тесты API заявок (доступ: admin — все, manager — свои объекты)."""

import pytest

from app.services.events import RequestStatusChangedEvent
from tests.integration.conftest import API


@pytest.fixture
def published_events(monkeypatch) -> list:
    """Перехват публикации событий (без реального RabbitMQ)."""
    events: list = []

    async def fake_publish(self, event):
        events.append(event)

    from app.services.events import EventPublisher

    monkeypatch.setattr(
        EventPublisher, "publish_request_status_changed", fake_publish
    )
    return events


async def test_list_unauthenticated_401(client):
    resp = await client.get(f"{API}/requests")
    assert resp.status_code == 401


async def test_admin_sees_all_requests(admin_client, request_obj):
    resp = await admin_client.get(f"{API}/requests")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == request_obj.id
    assert item["status"] == "new"
    assert item["phone"] == request_obj.phone


async def test_manager_without_objects_sees_nothing(manager_client, request_obj):
    resp = await manager_client.get(f"{API}/requests")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_manager_sees_only_own_objects(
    db, admin_client, manager_client, manager_user, obj, request_obj, object_data
):
    """Менеджер видит только заявки по своим объектам."""
    from app.domain.models import Object, Request

    # назначить менеджера на первый объект
    resp = await admin_client.put(
        f"{API}/objects/{obj.id}/managers",
        json={"user_ids": [manager_user.id]},
    )
    assert resp.status_code == 200

    # второй объект без менеджеров + заявка на него (заявки создаёт бот,
    # поэтому в тесте добавляем напрямую в БД)
    other = Object(category_id=obj.category_id, **object_data)
    db.add(other)
    await db.flush()
    other_request = Request(
        visitor_id=request_obj.visitor_id,
        object_id=other.id,
        phone=request_obj.phone,
    )
    db.add(other_request)
    await db.commit()

    # admin видит обе
    resp = await admin_client.get(f"{API}/requests")
    assert resp.json()["total"] == 2

    # менеджер — только по своему объекту
    resp = await manager_client.get(f"{API}/requests")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == request_obj.id

    # чужая заявка для менеджера — 404
    resp = await manager_client.get(f"{API}/requests/{other_request.id}")
    assert resp.status_code == 404


async def test_get_request(admin_client, request_obj):
    resp = await admin_client.get(f"{API}/requests/{request_obj.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == request_obj.id


async def test_get_missing_404(admin_client):
    resp = await admin_client.get(f"{API}/requests/9999")
    assert resp.status_code == 404


async def test_change_status_requires_manager(admin_client, request_obj):
    """Admin не может менять статус (Manager only)."""
    resp = await admin_client.post(
        f"{API}/requests/{request_obj.id}/status", json={"status": "approved"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Manager only"


async def test_change_status_not_your_object_403(
    admin_client, manager_client, request_obj
):
    """Менеджер без назначения на объект не может менять статус."""
    resp = await manager_client.post(
        f"{API}/requests/{request_obj.id}/status", json={"status": "approved"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Not your object"


async def test_change_status_flow(
    admin_client,
    manager_client,
    manager_user,
    obj,
    request_obj,
    published_events,
):
    """new -> approved -> completed; событие публикуется; неверный переход -> 400."""
    # назначить менеджера на объект
    resp = await admin_client.put(
        f"{API}/objects/{obj.id}/managers",
        json={"user_ids": [manager_user.id]},
    )
    assert resp.status_code == 200

    # new -> approved
    resp = await manager_client.post(
        f"{API}/requests/{request_obj.id}/status", json={"status": "approved"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["confirmed_at"] is not None

    # событие уведомления опубликовано (у visitor есть telegram_id)
    assert len(published_events) == 1
    event: RequestStatusChangedEvent = published_events[0]
    assert event.request_id == request_obj.id
    assert event.status == "approved"

    # approved -> completed
    resp = await manager_client.post(
        f"{API}/requests/{request_obj.id}/status", json={"status": "completed"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # completed -> approved запрещён
    resp = await manager_client.post(
        f"{API}/requests/{request_obj.id}/status", json={"status": "approved"}
    )
    assert resp.status_code == 400


async def test_change_status_missing_404(manager_client):
    resp = await manager_client.post(
        f"{API}/requests/9999/status", json={"status": "approved"}
    )
    assert resp.status_code == 404
