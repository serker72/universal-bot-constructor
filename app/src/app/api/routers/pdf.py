"""Роутер PDF: загрузка (admin) и получение (авторизованные)."""

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.domain.models import User
from app.repository.object import ObjectRepository
from app.services.pdf import PdfError, PdfService

router = APIRouter(route_class=DishkaRoute, tags=["pdf"])


@router.put("/objects/{object_id}/pdf", response_model=dict[str, str])
async def upload_pdf(
    object_id: int,
    file: UploadFile,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
    pdf: FromDishka[PdfService],
) -> dict[str, str]:
    """Загрузить PDF для объекта (multipart/form-data, только PDF, ≤20МБ)."""
    obj = await repo.get(object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    filename = file.filename or "document.pdf"
    content = await file.read()
    try:
        pdf.validate(filename, content)
    except PdfError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    # старый файл удалить, новый сохранить
    if obj.pdf_path:
        pdf.delete(obj.pdf_path)
    obj.pdf_path = pdf.save(object_id, filename, content)
    return {"pdf_path": str(obj.pdf_path)}


@router.get("/objects/{object_id}/pdf", response_class=FileResponse)
async def download_pdf(
    object_id: int,
    _user: FromDishka[User],  # любой авторизованный (admin/manager)
    repo: FromDishka[ObjectRepository],
    pdf: FromDishka[PdfService],
) -> FileResponse:
    """Получить PDF объекта (открывается в новой вкладке)."""
    obj = await repo.get(object_id)
    if obj is None:
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
