"""Интеграционные тесты API PDF (загрузка admin, скачивание авторизованным)."""

from tests.integration.conftest import API, PDF_CONTENT, PDF_FILENAME


def _upload_url(object_id: int) -> str:
    return f"{API}/objects/{object_id}/pdf"


async def test_upload_and_download(admin_client, manager_client, obj, settings):
    resp = await admin_client.put(
        _upload_url(obj.id),
        files={"file": (PDF_FILENAME, PDF_CONTENT, "application/pdf")},
    )
    assert resp.status_code == 200
    pdf_path = resp.json()["pdf_path"]
    assert pdf_path.startswith(f"{obj.id}/")
    assert pdf_path.endswith(".pdf")

    # файл на диске
    assert (settings.backend.pdf_data_dir / pdf_path).is_file()

    # скачивание: admin
    resp = await admin_client.get(_upload_url(obj.id))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == PDF_CONTENT

    # скачивание: manager (любой авторизованный)
    resp = await manager_client.get(_upload_url(obj.id))
    assert resp.status_code == 200


async def test_upload_replaces_old_file(admin_client, obj, settings):
    resp = await admin_client.put(
        _upload_url(obj.id),
        files={"file": (PDF_FILENAME, PDF_CONTENT, "application/pdf")},
    )
    first_path = resp.json()["pdf_path"]

    new_content = PDF_CONTENT + b" v2"
    resp = await admin_client.put(
        _upload_url(obj.id),
        files={"file": ("v2.pdf", new_content, "application/pdf")},
    )
    second_path = resp.json()["pdf_path"]
    assert second_path != first_path

    # старый файл удалён
    assert not (settings.backend.pdf_data_dir / first_path).exists()
    assert (settings.backend.pdf_data_dir / second_path).read_bytes() == new_content


async def test_upload_not_pdf_400(admin_client, obj):
    resp = await admin_client.put(
        _upload_url(obj.id),
        files={"file": ("doc.txt", b"text content", "text/plain")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


async def test_upload_invalid_content_400(admin_client, obj):
    resp = await admin_client.put(
        _upload_url(obj.id),
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert resp.status_code == 400


async def test_upload_missing_object_404(admin_client):
    resp = await admin_client.put(
        _upload_url(9999),
        files={"file": (PDF_FILENAME, PDF_CONTENT, "application/pdf")},
    )
    assert resp.status_code == 404


async def test_download_without_pdf_404(admin_client, obj):
    resp = await admin_client.get(_upload_url(obj.id))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "PDF not uploaded"


async def test_download_missing_object_404(admin_client):
    resp = await admin_client.get(_upload_url(9999))
    assert resp.status_code == 404


async def test_unauthenticated_401(client, obj):
    assert (await client.get(_upload_url(obj.id))).status_code == 401
    assert (
        await client.put(
            _upload_url(obj.id),
            files={"file": (PDF_FILENAME, PDF_CONTENT, "application/pdf")},
        )
    ).status_code == 401
