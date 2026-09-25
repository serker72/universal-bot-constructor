"""Роутер полей заявки (динамический конструктор заявки).

- Справочник полей (request_available_fields): CRUD — admin.
- Привязка полей к категории (состав формы заявки): GET/PUT — admin.
"""

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import FromDishka

from app.api.routing import TransactionalRoute
from app.api.deps import AdminUser, flush_or_400, get_or_404
from app.api.schemas.common import LimitQuery, OffsetQuery, Page
from app.bot.dialogs.time_items import MINUTES_STEP
from app.api.schemas.request_field import (
    CategoryFieldOut,
    CategoryFieldsIn,
    CategoryFieldsOut,
    RequestFieldIn,
    RequestFieldOut,
    RequestFieldUpdateIn,
)
from app.domain.models import RequestAvailableField, RequestFieldType
from app.domain.models.request_field_value import VALUE_TEXT_MAX_LENGTH
from app.repository.category import CategoryRepository
from app.repository.request_field import RequestFieldRepository

router = APIRouter(
    prefix="/request-fields", route_class=TransactionalRoute, tags=["request-fields"]
)

# Лимиты SELECT: Telegram показывает опции кнопками (текст кнопки — до 64
# символов), значение пишется в value_text
MAX_SELECT_OPTIONS = 50
MAX_OPTION_LENGTH = 64


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


def _is_number(value: object) -> bool:
    """int/float, но не bool (bool — подкласс int в Python)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# -- валидация meta_data по типу ---------------------------------------------


def _validate_meta_data(field_type: RequestFieldType, meta_data: dict | None) -> None:
    """Проверка параметров поля по типу (значения типизированы, пустые запрещены).

    - SELECT — options: непустой список непустых строк ≤ MAX_OPTION_LENGTH;
    - TIME — minute_step: целое, делитель 60 (1..30);
    - NUMBER — min/max: числа, min ≤ max;
    - TEXT — max_length: целое 1..VALUE_TEXT_MAX_LENGTH (длина колонки value_text).
    """
    if meta_data is None:
        if field_type == RequestFieldType.SELECT:
            raise _bad_request("SELECT-поле требует meta_data с непустым списком options")
        return
    if field_type == RequestFieldType.SELECT:
        options = meta_data.get("options")
        if (
            not isinstance(options, list)
            or not options
            or not all(isinstance(o, str) and o.strip() for o in options)
        ):
            raise _bad_request("meta_data.options — непустой список строк")
        if len(options) > MAX_SELECT_OPTIONS:
            raise _bad_request(f"meta_data.options — не более {MAX_SELECT_OPTIONS} вариантов")
        if any(len(o) > MAX_OPTION_LENGTH for o in options):
            raise _bad_request(
                f"meta_data.options — вариант не длиннее {MAX_OPTION_LENGTH} символов"
            )
        if len({o.strip() for o in options}) != len(options):
            raise _bad_request("meta_data.options — варианты не должны повторяться")
    if field_type == RequestFieldType.TIME:
        step = meta_data.get("minute_step", MINUTES_STEP)
        if not _is_int(step) or not (1 <= step <= 30) or 60 % step != 0:
            raise _bad_request("meta_data.minute_step — делитель 60 (1..30)")
    if field_type == RequestFieldType.NUMBER:
        minimum = meta_data.get("min")
        maximum = meta_data.get("max")
        for name, value in (("min", minimum), ("max", maximum)):
            if value is not None and not _is_number(value):
                raise _bad_request(f"meta_data.{name} — число")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise _bad_request("meta_data.min не может быть больше max")
    if field_type == RequestFieldType.TEXT and "max_length" in meta_data:
        max_length = meta_data["max_length"]
        if not _is_int(max_length) or not (1 <= max_length <= VALUE_TEXT_MAX_LENGTH):
            raise _bad_request(
                f"meta_data.max_length — целое число 1..{VALUE_TEXT_MAX_LENGTH}"
            )


# -- CRUD справочника ----------------------------------------------------------


@router.get("", response_model=Page[RequestFieldOut])
async def list_fields(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[RequestFieldRepository],
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
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
        raise _bad_request("Code already exists")
    field = RequestAvailableField(
        code=data.code,
        type=data.type,
        label=data.label,
        is_required_default=data.is_required_default,
        meta_data=data.meta_data,
    )
    repo.session.add(field)
    await flush_or_400(repo.session, "Code already exists")
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
    """Обновить поле справочника (PATCH: только переданные поля).

    ``meta_data: null`` — очистить параметры (ключ отсутствует — не менять).
    """
    field = get_or_404(await repo.get(field_id), "Field not found")
    fields = data.model_fields_set
    new_type = data.type if data.type is not None else field.type
    new_meta = data.meta_data if "meta_data" in fields else field.meta_data
    # тип менялся — meta_data валидируем заново с новым типом
    _validate_meta_data(new_type, new_meta)
    if data.code is not None and data.code != field.code:
        if await repo.get_by_code(data.code):
            raise _bad_request("Code already exists")
        field.code = data.code
    if data.type is not None:
        field.type = data.type
    if data.label is not None:
        field.label = data.label
    if data.is_required_default is not None:
        field.is_required_default = data.is_required_default
    if "meta_data" in fields:
        field.meta_data = data.meta_data
    await flush_or_400(repo.session, "Code already exists")
    await repo.session.refresh(field)
    return RequestFieldOut.model_validate(field)


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field(
    field_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[RequestFieldRepository],
) -> None:
    """Удалить поле справочника (запрещено, если есть значения заявок — RESTRICT).

    Привязки поля к категориям удаляются каскадно (ON DELETE CASCADE).
    """
    field = get_or_404(await repo.get(field_id), "Field not found")
    if await repo.count_request_values(field_id):
        raise _bad_request("Field has request values and cannot be deleted")
    await repo.delete(field)
    # session.delete() не выполняет flush — FK RESTRICT иначе всплывёт
    # на commit после формирования ответа
    await flush_or_400(repo.session, "Field has request values and cannot be deleted")


# -- привязка полей к категории ------------------------------------------------


async def _category_fields_out(
    category_id: int, repo: RequestFieldRepository
) -> CategoryFieldsOut:
    """Состав полей формы заявки категории (схема ответа)."""
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


@router.get("/categories/{category_id}/fields", response_model=CategoryFieldsOut)
async def get_category_fields(
    category_id: int,
    _admin: FromDishka[AdminUser],
    categories: FromDishka[CategoryRepository],
    repo: FromDishka[RequestFieldRepository],
) -> CategoryFieldsOut:
    """Состав полей формы заявки категории."""
    get_or_404(await categories.get(category_id), "Category not found")
    return await _category_fields_out(category_id, repo)


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
        raise _bad_request("Duplicate field_id in list")
    found = await repo.find(RequestAvailableField.id.in_(target_ids))
    found_ids = {f.id for f in found}
    missing = set(target_ids) - found_ids
    if missing:
        raise _bad_request(
            f"Field(s) not found: {', '.join(str(i) for i in sorted(missing))}"
        )
    # diff: удалить лишние, добавить/обновить переданные
    # (текущие привязки читаются один раз, а не на каждой итерации)
    existing = {
        link.field_id: link
        for link, _f in await repo.list_category_fields(category_id)
    }
    target_set = set(target_ids)
    for field_id in set(existing) - target_set:
        await repo.remove_category_field(category_id, field_id)
    for link in data.fields:
        current = existing.get(link.field_id)
        if current is None:
            await repo.add_category_field(
                category_id, link.field_id, link.sort_order, link.is_required
            )
        else:
            current.sort_order = link.sort_order
            current.is_required = link.is_required
    await repo.session.flush()
    return await _category_fields_out(category_id, repo)
