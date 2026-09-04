"""Сервис PDF-файлов: сохранение, чтение, удаление."""

import re
from pathlib import Path
from uuid import uuid4

from app.config.settings import Settings


class PdfError(Exception):
    """Некорректный PDF-файл (формат, размер)."""


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class PdfService:
    """Работа с PDF на диске (каталог pdf_data_dir)."""

    def __init__(self, settings: Settings) -> None:
        self.base_dir = settings.backend.pdf_data_dir
        self.max_size = settings.backend.max_pdf_size_mb * 1024 * 1024

    def validate(self, filename: str, content: bytes) -> None:
        """Проверить имя и содержимое файла (только PDF, ≤ max_size)."""
        if not filename.lower().endswith(".pdf"):
            raise PdfError("only PDF files are allowed")
        if not content.startswith(b"%PDF-"):
            raise PdfError("invalid PDF content")
        if len(content) > self.max_size:
            raise PdfError("file too large")

    def save(self, object_id: int, filename: str, content: bytes) -> str:
        """Сохранить файл, вернуть путь относительно базового каталога."""
        safe = _SAFE_NAME.sub("_", Path(filename).name)[:80] or "document.pdf"
        rel_dir = Path(str(object_id))
        abs_dir = self.base_dir / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        rel_path = rel_dir / f"{uuid4().hex}_{safe}"
        (self.base_dir / rel_path).write_bytes(content)
        return str(rel_path)

    def open(self, rel_path: str) -> Path:
        """Открыть файл по относительному пути (для отправки клиенту)."""
        path = self.base_dir / rel_path
        if not path.is_file():
            raise PdfError("file not found")
        return path

    def delete(self, rel_path: str) -> None:
        """Удалить файл (если существует)."""
        path = self.base_dir / rel_path
        path.unlink(missing_ok=True)
