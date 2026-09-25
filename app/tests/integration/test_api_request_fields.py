"""Интеграционные тесты API полей заявки (справочник + привязки категорий)."""

import pytest


from tests.integration.conftest import API


# -- CRUD справочника ---------------------------------------------------------


async def test_create_and_get_field(admin_client):
    resp = await admin_client.post(
        f"{API}/request-fields",
        json={
            "code": "guests_count",
            "type": "number",
            "label": "Количество гостей",
            "is_required_default": True,
            "meta_data": {"min": 1, "max": 100},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "guests_count"
    assert body["type"] == "number"
    assert body["meta_data"] == {"min": 1, "max": 100}

    resp = await admin_client.get(f"{API}/request-fields/{body['id']}")
    assert resp.status_code == 200
    assert resp.json()["code"] == "guests_count"


async def test_create_duplicate_code_400(admin_client):
    data = {"code": "dup_code", "type": "text", "label": "Поле 1"}
    await admin_client.post(f"{API}/request-fields", json=data)
    resp = await admin_client.post(f"{API}/request-fields", json=data)
    assert resp.status_code == 400


async def test_select_requires_options_400(admin_client):
    """SELECT-поле без options — 400."""
    resp = await admin_client.post(
        f"{API}/request-fields",
        json={"code": "bad_select", "type": "select", "label": "Выбор"},
    )
    assert resp.status_code == 400


async def test_time_minute_step_validation_400(admin_client):
    """TIME-поле с некорректным шагом минут — 400."""
    resp = await admin_client.post(
        f"{API}/request-fields",
        json={
            "code": "bad_time",
            "type": "time",
            "label": "Время",
            "meta_data": {"minute_step": 7},  # не делитель 60
        },
    )
    assert resp.status_code == 400


async def test_patch_field(admin_client, field_text):
    resp = await admin_client.patch(
        f"{API}/request-fields/{field_text.id}",
        json={"label": "Новый комментарий", "is_required_default": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "Новый комментарий"
    assert body["is_required_default"] is True
    assert body["code"] == field_text.code  # не менялось


async def test_delete_field(admin_client, field_text):
    resp = await admin_client.delete(f"{API}/request-fields/{field_text.id}")
    assert resp.status_code == 204
    resp = await admin_client.get(f"{API}/request-fields/{field_text.id}")
    assert resp.status_code == 404


async def test_delete_field_with_values_400(admin_client, request_obj, field_text):
    """Поле со значениями заявок удалить нельзя (RESTRICT)."""
    resp = await admin_client.delete(f"{API}/request-fields/{field_text.id}")
    assert resp.status_code == 400


async def test_fields_unauthenticated_401(client):
    resp = await client.get(f"{API}/request-fields")
    assert resp.status_code == 401


# -- привязка к категории -------------------------------------------------------


async def test_set_and_get_category_fields(admin_client, category, field_text, field_time):
    """PUT полного состава полей; GET возвращает состав с сортировкой."""
    resp = await admin_client.put(
        f"{API}/request-fields/categories/{category.id}/fields",
        json={
            "fields": [
                {"field_id": field_text.id, "sort_order": 2, "is_required": False},
                {"field_id": field_time.id, "sort_order": 1, "is_required": True},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["fields"]) == 2
    # сортировка по sort_order: время (1) → комментарий (2)
    assert body["fields"][0]["field"]["id"] == field_time.id
    assert body["fields"][0]["is_required"] is True
    assert body["fields"][1]["field"]["id"] == field_text.id

    # GET — тот же состав
    resp = await admin_client.get(
        f"{API}/request-fields/categories/{category.id}/fields"
    )
    assert resp.status_code == 200
    assert len(resp.json()["fields"]) == 2


async def test_set_category_fields_unknown_field_400(admin_client, category):
    resp = await admin_client.put(
        f"{API}/request-fields/categories/{category.id}/fields",
        json={"fields": [{"field_id": 9999, "sort_order": 1, "is_required": False}]},
    )
    assert resp.status_code == 400


async def test_set_category_fields_duplicates_400(
    admin_client, category, field_text
):
    resp = await admin_client.put(
        f"{API}/request-fields/categories/{category.id}/fields",
        json={
            "fields": [
                {"field_id": field_text.id, "sort_order": 1, "is_required": False},
                {"field_id": field_text.id, "sort_order": 2, "is_required": True},
            ]
        },
    )
    assert resp.status_code == 400


async def test_replace_category_fields_removes_old(
    admin_client, category, field_text, field_time
):
    """Замена состава: поле, не переданное в PUT, отвязывается."""
    # привязать оба
    await admin_client.put(
        f"{API}/request-fields/categories/{category.id}/fields",
        json={
            "fields": [
                {"field_id": field_text.id, "sort_order": 1, "is_required": False},
                {"field_id": field_time.id, "sort_order": 2, "is_required": True},
            ]
        },
    )
    # заменить только одним
    resp = await admin_client.put(
        f"{API}/request-fields/categories/{category.id}/fields",
        json={"fields": [{"field_id": field_text.id, "sort_order": 1, "is_required": False}]},
    )
    assert resp.status_code == 200
    assert len(resp.json()["fields"]) == 1
    assert resp.json()["fields"][0]["field"]["id"] == field_text.id


async def test_category_fields_missing_category_404(admin_client):
    resp = await admin_client.get(f"{API}/request-fields/categories/9999/fields")
    assert resp.status_code == 404


async def test_delete_field_linked_to_category(admin_client, category_with_fields, field_text):
    """Поле, привязанное к категории (без значений заявок), удаляется каскадно."""
    resp = await admin_client.delete(f"{API}/request-fields/{field_text.id}")
    assert resp.status_code == 204
    resp = await admin_client.get(
        f"{API}/request-fields/categories/{category_with_fields.id}/fields"
    )
    ids = [f["field"]["id"] for f in resp.json()["fields"]]
    assert field_text.id not in ids


@pytest.mark.parametrize(
    ("field_type", "meta"),
    [
        ("number", {"min": ""}),
        ("number", {"min": 5, "max": 1}),
        ("number", {"max": "10"}),
        ("text", {"max_length": ""}),
        ("text", {"max_length": 5000}),
        ("time", {"minute_step": True}),
        ("select", {"options": ["x" * 65]}),
    ],
)
async def test_meta_data_types_validated_400(admin_client, field_type, meta):
    resp = await admin_client.post(
        f"{API}/request-fields",
        json={"code": "bad_meta", "type": field_type, "label": "L", "meta_data": meta},
    )
    assert resp.status_code == 400


async def test_patch_meta_data_null_clears(admin_client, field_text):
    resp = await admin_client.patch(
        f"{API}/request-fields/{field_text.id}", json={"meta_data": None}
    )
    assert resp.status_code == 200
    assert resp.json()["meta_data"] is None
    # ключ отсутствует — не менять
    resp = await admin_client.patch(
        f"{API}/request-fields/{field_text.id}", json={"label": "X"}
    )
    assert resp.json()["meta_data"] is None
