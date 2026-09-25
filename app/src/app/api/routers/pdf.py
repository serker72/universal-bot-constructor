"""Роутер PDF: загрузка (admin) и получение (авторизованные)."""

import asyncio

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from dishka.integrations.fastapi import FromDishka

from app.api.routing import TransactionalRoute
from app.api.access import visible_object_ids
from app.api.deps import AdminUser, get_or_404
from app.domain.models import User, UserRole
from app.repository.object import ObjectRepository
from app.services.pdf import PdfError, PdfService

router = APIRouter(route_class=TransactionalRoute, tags=["pdf"])


@router.put("/objects/{object_id}/pdf", response_model=dict[str, str])
async def upload_pdf(
    object_id: int,
    file: UploadFile,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
    pdf: FromDishka[PdfService],
) -> dict[str, str]:
    """Загрузить PDF для объекта (multipart/form-data, только PDF, ≤20МБ).

    Порядок: новый файл → commit pdf_path → удаление старого файла. При сбое
    commit новый файл удаляется, а старый остаётся на месте (pdf_path в БД
    не указывает на удалённый файл).
    """
    obj = get_or_404(await repo.get(object_id), "Object not found")
    filename = file.filename or "document.pdf"
    # размер проверяем ДО чтения: файл не грузится в память целиком,
    # если он заведомо больше лимита
    declared = file.size
    if declared is not None and declared > pdf.max_size:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file too large")
    content = await file.read()
    if len(content) > pdf.max_size:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file too large")
    try:
        pdf.validate(filename, content)
    except PdfError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    old_path = obj.pdf_path
    # файловый I/O — в пуле потоков (не блокирует event loop)
    new_path = await asyncio.to_thread(pdf.save, object_id, filename, content)
    obj.pdf_path = new_path
    # кешированный file_id Telegram относится к старому файлу
    obj.telegram_file_id = None
    try:
        await repo.session.commit()
    except Exception:
        await asyncio.to_thread(pdf.delete, new_path)
        raise
    if old_path:
        await asyncio.to_thread(pdf.delete, old_path)
    return {"pdf_path": str(new_path)}


@router.get("/objects/{object_id}/pdf", response_class=FileResponse)
async def download_pdf(
    object_id: int,
    user: FromDishka[User],  # любой авторизованный (admin/manager)
    repo: FromDishka[ObjectRepository],
    pdf: FromDishka[PdfService],
) -> FileResponse:
    """Получить PDF объекта (открывается в новой вкладке).

    Менеджер — только своих объектов (та же проверка, что в GET /objects/{id});
    PDF неактивного объекта доступен только admin.
    """
    obj = get_or_404(await repo.get(object_id), "Object not found")
    object_ids = await visible_object_ids(user, repo)
    if object_ids is not None and obj.id not in object_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    if not obj.is_active and user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    if not obj.pdf_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF not uploaded")
    try:
        path = pdf.open(obj.pdf_path)
    except PdfError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"object-{object_id}.pdf",
        content_disposition_type="inline",
    )
