"""Тесты PDF-сервиса (app.services.pdf)."""

import pytest

from app.services.pdf import PdfError, PdfService

PDF_CONTENT = b"%PDF-1.4 fake pdf content"


@pytest.fixture
def service(settings) -> PdfService:
    return PdfService(settings)


class TestValidate:
    def test_valid(self, service: PdfService):
        service.validate("document.pdf", PDF_CONTENT)

    def test_wrong_extension(self, service: PdfService):
        with pytest.raises(PdfError, match="only PDF"):
            service.validate("document.txt", PDF_CONTENT)

    def test_invalid_content(self, service: PdfService):
        with pytest.raises(PdfError, match="invalid PDF"):
            service.validate("document.pdf", b"not a pdf at all")

    def test_too_large(self, service: PdfService):
        big = PDF_CONTENT + b"0" * service.max_size
        with pytest.raises(PdfError, match="too large"):
            service.validate("document.pdf", big)


class TestSaveOpenDelete:
    def test_save_returns_relative_path(self, service: PdfService, settings):
        rel_path = service.save(7, "Мой документ.pdf", PDF_CONTENT)

        path = settings.backend.pdf_data_dir / rel_path
        assert path.is_file()
        assert path.read_bytes() == PDF_CONTENT
        # файл кладётся в каталог с id объекта, имя очищается от небезопасных символов
        assert rel_path.startswith("7/")
        assert rel_path.endswith(".pdf")

    def test_open_existing(self, service: PdfService):
        rel_path = service.save(1, "doc.pdf", PDF_CONTENT)
        assert service.open(rel_path).is_file()

    def test_open_missing_raises(self, service: PdfService):
        with pytest.raises(PdfError, match="not found"):
            service.open("999/missing.pdf")

    def test_delete(self, service: PdfService):
        rel_path = service.save(1, "doc.pdf", PDF_CONTENT)
        service.delete(rel_path)
        with pytest.raises(PdfError):
            service.open(rel_path)

    def test_delete_missing_is_noop(self, service: PdfService):
        service.delete("999/never-existed.pdf")

    def test_save_unsafe_name_replaced(self, service: PdfService):
        """Небезопасные символы в имени заменяются на подчёркивания."""
        rel_path = service.save(1, "мой файл: v1?.pdf", PDF_CONTENT)
        name = rel_path.split("_", 1)[1]
        assert all(c.isalnum() or c in "._-" for c in name)

    def test_save_empty_name_fallback(self, service: PdfService):
        """Пустое имя -> fallback document.pdf."""
        rel_path = service.save(1, "", PDF_CONTENT)
        assert rel_path.split("_", 1)[1] == "document.pdf"
