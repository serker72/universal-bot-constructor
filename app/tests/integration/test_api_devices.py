"""Интеграционные тесты API устройств (только admin, read-only)."""

from datetime import datetime, timezone

import pytest
from tests.integration.conftest import API


@pytest.fixture
async def device(db, admin_user):
    """Устройство пользователя в БД."""
    from app.domain.models import Device

    now = datetime.now(timezone.utc)
    device = Device(
        user_id=admin_user.id,
        device_id="device-abc-123",
        user_agent="pytest-agent",
        created_at=now,
        last_seen_at=now,
    )
    db.add(device)
    await db.commit()
    return device


async def test_list_unauthenticated_401(client):
    resp = await client.get(f"{API}/devices")
    assert resp.status_code == 401


async def test_manager_forbidden(manager_client):
    resp = await manager_client.get(f"{API}/devices")
    assert resp.status_code == 403


async def test_list_devices(admin_client, device):
    resp = await admin_client.get(f"{API}/devices")
    assert resp.status_code == 200
    body = resp.json()
    # 2 устройства: созданное при login (admin_client) + fixture device
    assert body["total"] == 2
    by_device_id = {i["device_id"]: i for i in body["items"]}
    assert by_device_id[device.device_id]["user_agent"] == "pytest-agent"


async def test_list_filter_by_user(admin_client, device, admin_user):
    resp = await admin_client.get(f"{API}/devices", params={"user_id": admin_user.id})
    assert resp.status_code == 200
    # 2 устройства admin: созданное при login + fixture device
    assert resp.json()["total"] == 2

    resp = await admin_client.get(f"{API}/devices", params={"user_id": 9999})
    assert resp.json()["total"] == 0


async def test_get_device(admin_client, device):
    resp = await admin_client.get(f"{API}/devices/{device.id}")
    assert resp.status_code == 200
    assert resp.json()["device_id"] == "device-abc-123"


async def test_get_missing_404(admin_client):
    resp = await admin_client.get(f"{API}/devices/9999")
    assert resp.status_code == 404
