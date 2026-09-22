"""Репозиторий полей заявки: справочник, привязки категорий, значения."""

from collections.abc import Sequence

from sqlalchemy import asc, func, select

from app.domain.models import (
    RequestAvailableField,
    RequestCategoryField,
    RequestField,
)
from app.repository.base import BaseRepository


class RequestFieldRepository(BaseRepository[RequestAvailableField]):
    """Справочник доступных полей + привязки категорий + значения заявок."""

    model = RequestAvailableField

    # -- справочник ----------------------------------------------------------

    async def get_by_code(self, code: str) -> RequestAvailableField | None:
        """Поле справочника по тех. коду."""
        return await self.find_one(RequestAvailableField.code == code)

    # -- привязки к категории --------------------------------------------------

    async def list_category_fields(
        self, category_id: int
    ) -> Sequence[tuple[RequestCategoryField, RequestAvailableField]]:
        """Поля категории (привязка + поле) в порядке sort_order."""
        stmt = (
            select(RequestCategoryField, RequestAvailableField)
            .join(
                RequestAvailableField,
                RequestCategoryField.field_id == RequestAvailableField.id,
            )
            .where(RequestCategoryField.category_id == category_id)
            .order_by(asc(RequestCategoryField.sort_order), asc(RequestCategoryField.id))
        )
        return (await self.session.execute(stmt)).all()

    async def list_category_field_ids(self, category_id: int) -> list[int]:
        """Id полей, привязанных к категории."""
        links = await self.session.scalars(
            select(RequestCategoryField.field_id).where(
                RequestCategoryField.category_id == category_id
            )
        )
        return list(links)

    async def add_category_field(
        self,
        category_id: int,
        field_id: int,
        sort_order: int,
        is_required: bool,
    ) -> RequestCategoryField:
        """Привязать поле к категории."""
        link = RequestCategoryField(
            category_id=category_id,
            field_id=field_id,
            sort_order=sort_order,
            is_required=is_required,
        )
        self.session.add(link)
        return link

    async def remove_category_field(
        self, category_id: int, field_id: int
    ) -> None:
        """Отвязать поле от категории."""
        link = (
            await self.session.scalars(
                select(RequestCategoryField).where(
                    RequestCategoryField.category_id == category_id,
                    RequestCategoryField.field_id == field_id,
                )
            )
        ).first()
        if link is not None:
            await self.session.delete(link)

    # -- значения заявок -------------------------------------------------------

    async def count_request_values(self, field_id: int) -> int:
        """Количество значений поля в заявках (проверка перед удалением поля)."""
        stmt = (
            select(func.count())
            .select_from(RequestField)
            .where(RequestField.field_id == field_id)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def add_values(
        self, request_id: int, answers: dict[int, str | None]
    ) -> list[RequestField]:
        """Сохранить значения полей заявки ({field_id: value_text})."""
        values = [
            RequestField(
                request_id=request_id,
                field_id=field_id,
                value_text=value,
            )
            for field_id, value in answers.items()
        ]
        self.session.add_all(values)
        return values

    async def list_values(
        self, request_id: int
    ) -> Sequence[tuple[RequestField, RequestAvailableField]]:
        """Значения полей заявки (значение + поле справочника)."""
        stmt = (
            select(RequestField, RequestAvailableField)
            .join(
                RequestAvailableField,
                RequestField.field_id == RequestAvailableField.id,
            )
            .where(RequestField.request_id == request_id)
            .order_by(asc(RequestAvailableField.id))
        )
        return (await self.session.execute(stmt)).all()
