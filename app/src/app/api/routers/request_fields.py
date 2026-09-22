"""Роутер полей заявки (динамический конструктор заявки).

- Справочник полей (request_available_fields): CRUD — admin.
- Привязка полей к категории (состав формы заявки): GET/PUT — admin.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser, get_or_404
from app.api.schemas.common import Page
from app.api.schemas.request_field import (
    CategoryFieldOut,
    CategoryFieldsIn,
    CategoryFieldsOut,
    RequestFieldIn,
    RequestFieldOut,
    RequestFieldUpdateIn,
)
from app.domain.models import RequestAvailableField, RequestFieldType
from app.repository.category import CategoryRepository
from app.repository.request_field import RequestFieldRepository

router = APIRouter(
    prefix="/request-fields", route_class=DishkaRoute, tags=["request-fields"]
)


# -- валидация meta_data по типу ---------------------------------------------


def _validate_meta_data(field_type: RequestFieldType, meta_data: dict | None) -> None:
    """Проверка параметров поля по типу (SELECT — options, TIME — minute_step)."""
    if meta_data is None:
        if field_type == RequestFieldType.SELECT:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "SELECT-поле требует meta_data с непустым списком options",
            )
        return
    if field_type == RequestFieldType.SELECT:
        options = meta_data.get("options")
        if (
            not isinstance(options, list)
            or not options
            or not all(isinstance(o, str) and o.strip() for o in options)
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "meta_data.options — непустой список строк",
            )
    if field_type == RequestFieldType.TIME:
        step = meta_data.get("minute_step", 5)
        if not isinstance(step, int) or not (1 <= step <= 30) or 60 % step != 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "meta_data.minute_step — делитель 60 (1..30)",
            )


# -- CRUD справочника ----------------------------------------------------------


@router.get("", response_model=Page[RequestFieldOut])
async def list_fields(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[RequestFieldRepository],
    limit: int = 100,
    offset: int = 0,
) -> Page[RequestFieldOut]:
    """Список полей справочника."""
    items = await repo.find(limit=limit, offset=offset, order_by=RequestAvailableField.id)
    total = await repo.count()
    return Page(
        items=[RequestFieldOut.model_validate(f) for f in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=RequestFieldOut, status_code=status.HTTP_201_CREATED)
async def create_field(
    data: RequestFieldIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[RequestFieldRepository],
) -> RequestFieldOut:
    """Создать поле справочника."""
    _validate_meta_data(data.type, data.meta_data)
    if await repo.get_by_code(data.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code already exists")
    field = RequestAvailableField(
        code=data.code,
        type=data.type,
        label=data.label,
        is_required_default=data.is_required_default,
        meta_data=data.meta_data,
    )
    try:
        await repo.add(field)
    except IntegrityError:
        await repo.session.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Code already exists"
        ) from None
    return RequestFieldOut.model_validate(field)


@router.get("/{field_id}", response_model=RequestFieldOut)
async def get_field(
    field_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[RequestFieldRepository],
) -> RequestFieldOut:
    """Получить поле справочника."""
    field = get_or_404(await repo.get(field_id), "Field not found")
    return RequestFieldOut.model_validate(field)


@router.patch("/{field_id}", response_model=RequestFieldOut)
async def update_field(
    field_id: int,
    data: RequestFieldUpdateIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[RequestFieldRepository],
) -> RequestFieldOut:
    """Обновить поле справочника (PATCH: только переданные поля)."""
    field = get_or_404(await repo.get(field_id), "Field not found")
    new_type = data.type if data.type is not None else field.type
    new_meta = data.meta_data if data.meta_data is not None else field.meta_data
    # тип менялся — meta_data валидируем заново с новым типом
    _validate_meta_data(new_type, new_meta)
    if data.code is not None and data.code != field.code:
        if await repo.get_by_code(data.code):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code already exists")
        field.code = data.code
    if data.type is not None:
        field.type = data.type
    if data.label is not None:
        field.label = data.label
    if data.is_required_default is not None:
        field.is_required_default = data.is_required_default
    if data.meta_data is not None:
        field.meta_data = data.meta_data
    return RequestFieldOut.model_validate(field)


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field(
    field_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[RequestFieldRepository],
) -> None:
    """Удалить поле справочника (запрещено, если есть значения заявок — RESTRICT)."""
    field = get_or_404(await repo.get(field_id), "Field not found")
    if await repo.count_request_values(field_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Field has request values and cannot be deleted",
        )
    try:
        await repo.delete(field)
        # session.delete() не выполняет flush — FK RESTRICT иначе всплывёт
        # на commit после формирования ответа
        await repo.session.flush()
    except IntegrityError:
        await repo.session.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Field has request values and cannot be deleted",
        ) from None


# -- привязка полей к категории ------------------------------------------------


@router.get("/categories/{category_id}/fields", response_model=CategoryFieldsOut)
async def get_category_fields(
    category_id: int,
    _admin: FromDishka[AdminUser],
    categories: FromDishka[CategoryRepository],
    repo: FromDishka[RequestFieldRepository],
) -> CategoryFieldsOut:
    """Состав полей формы заявки категории."""
    get_or_404(await categories.get(category_id), "Category not found")
    rows = await repo.list_category_fields(category_id)
    return CategoryFieldsOut(
        category_id=category_id,
        fields=[
            CategoryFieldOut(
                field=RequestFieldOut.model_validate(f),
                sort_order=link.sort_order,
                is_required=link.is_required,
            )
            for link, f in rows
        ],
    )


@router.put("/categories/{category_id}/fields", response_model=CategoryFieldsOut)
async def set_category_fields(
    category_id: int,
    data: CategoryFieldsIn,
    _admin: FromDishka[AdminUser],
    categories: FromDishka[CategoryRepository],
    repo: FromDishka[RequestFieldRepository],
) -> CategoryFieldsOut:
    """Заменить состав полей формы заявки категории (полный список)."""
    get_or_404(await categories.get(category_id), "Category not found")
    # все поля должны существовать (batch-запрос)
    target_ids = [link.field_id for link in data.fields]
    if len(set(target_ids)) != len(target_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Duplicate field_id in list"
        )
    found = await repo.find(RequestAvailableField.id.in_(target_ids))
    found_ids = {f.id for f in found}
    missing = set(target_ids) - found_ids
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Field(s) not found: {', '.join(str(i) for i in sorted(missing))}",
        )
    # diff: удалить лишние, добавить/обновить переданные
    current_ids = set(await repo.list_category_field_ids(category_id))
    target_set = set(target_ids)
    for field_id in current_ids - target_set:
        await repo.remove_category_field(category_id, field_id)
    for link in data.fields:
        if link.field_id in target_set - current_ids:
            await repo.add_category_field(
                category_id, link.field_id, link.sort_order, link.is_required
            )
        else:
            # существующая привязка: обновить sort_order/is_required
            rows = {
                row.field_id: row
                for row, _f in await repo.list_category_fields(category_id)
            }
            existing = rows.get(link.field_id)
            if existing is not None:
                existing.sort_order = link.sort_order
                existing.is_required = link.is_required
    return await get_category_fields(
        category_id, _admin, categories, repo  # type: ignore[arg-type]
    )