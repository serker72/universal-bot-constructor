"""Меню и клавиатуры бота.

Единая схема callback-данных: только классы CallbackData (aiogram),
без raw-строк. Поля со значениями по умолчанию не пакуются
(CategoryCB() -> "cat", CategoryCB(page=1) -> "cat:None:1").
"""

from aiogram import types
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.statuses import STATUS_EMOJI


class CategoryCB(CallbackData, prefix="cat"):
    """Список категорий (category_id=None) или выбор категории."""

    category_id: int | None = None
    page: int = 0


class ObjectCB(CallbackData, prefix="obj"):
    """Список объектов категории (object_id=None) или выбор объекта."""

    category_id: int
    object_id: int | None = None
    page: int = 0


class ObjectActionCB(CallbackData, prefix="objact"):
    """Получить PDF объекта."""

    object_id: int


class CreateRequestCB(CallbackData, prefix="reqnew"):
    """Начать создание заявки на объект."""

    object_id: int


class RequestCB(CallbackData, prefix="req"):
    """Мои заявки: список (request_id=None), просмотр, отмена."""

    request_id: int | None = None
    page: int = 0
    cancel: bool = False


class ConsentCB(CallbackData, prefix="consent"):
    """Согласие на обработку ПД."""

    approved: bool = True


class MenuCB(CallbackData, prefix="menu"):
    """Возврат в главное меню (список категорий)."""


class PointSelectCB(CallbackData, prefix="pt"):
    """Выбор точки из селектора."""

    point_id: int


class PointListCB(CallbackData, prefix="ptlist"):
    """Пагинация селектора точек."""

    page: int = 0


class ChangePointCB(CallbackData, prefix="ptchange"):
    """Кнопка «Сменить филиал» в меню."""


class PointCancelCB(CallbackData, prefix="ptcancel"):
    """Отмена выбора точки (возврат в меню)."""


def _add_pager(
    builder: InlineKeyboardBuilder,
    *,
    page: int,
    total: int,
    prev_cb: str,
    next_cb: str,
) -> None:
    """Строка пагинации ◀️ N/M ▶️ (если больше одной страницы)."""
    if total > 1:
        row = []
        if page > 0:
            row.append(("◀️", prev_cb))
        row.append((f"{page + 1}/{total}", "noop"))
        if page < total - 1:
            row.append(("▶️", next_cb))
        builder.row(
            *[types.InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
        )


def main_menu_keyboard():
    """Только «Главное меню» — когда возвращаться некуда (пустой список)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🏠 Главное меню", callback_data=MenuCB().pack())
    )
    return builder.as_markup()


def request_cancelled_keyboard():
    """Результат отмены заявки: назад к списку своих заявок и в главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="◀️ Мои заявки", callback_data=RequestCB().pack())
    )
    builder.row(
        types.InlineKeyboardButton(text="🏠 Главное меню", callback_data=MenuCB().pack())
    )
    return builder.as_markup()


def categories_keyboard(items, page: int, total: int, show_change_point: bool = False):
    """Главное меню: список категорий с пагинацией (1 кнопка в строке).

    ``show_change_point`` — добавить кнопку «Сменить филиал» (показывается
    только при >1 активной точке; вычисляется в хендлере).
    """
    builder = InlineKeyboardBuilder()
    for cat in items:
        builder.button(
            text=cat.name,
            callback_data=CategoryCB(category_id=cat.id).pack(),
        )
    builder.adjust(1)
    _add_pager(
        builder,
        page=page,
        total=total,
        prev_cb=CategoryCB(page=page - 1).pack(),
        next_cb=CategoryCB(page=page + 1).pack(),
    )
    builder.row(
        types.InlineKeyboardButton(text="📋 Мои заявки", callback_data=RequestCB().pack())
    )
    if show_change_point:
        builder.row(
            types.InlineKeyboardButton(
                text="🏳 Сменить филиал", callback_data=ChangePointCB().pack()
            )
        )
    return builder.as_markup()


def objects_keyboard(category_id: int, items, page: int, total: int):
    """Список объектов категории с пагинацией (1 кнопка в строке)."""
    builder = InlineKeyboardBuilder()
    for obj in items:
        builder.button(
            text=obj.name,
            callback_data=ObjectCB(category_id=category_id, object_id=obj.id).pack(),
        )
    builder.adjust(1)
    _add_pager(
        builder,
        page=page,
        total=total,
        prev_cb=ObjectCB(category_id=category_id, page=page - 1).pack(),
        next_cb=ObjectCB(category_id=category_id, page=page + 1).pack(),
    )
    # возврат из списка объектов: список категорий — это главное меню,
    # отдельная кнопка «Категории» не нужна
    builder.row(
        types.InlineKeyboardButton(
            text="🏠 Главное меню", callback_data=MenuCB().pack()
        )
    )
    return builder.as_markup()


def object_keyboard(category_id: int, object_id: int, request_button_text: str | None = None):
    """Страница объекта: PDF, заявка, назад (1 кнопка в строке).

    ``request_button_text`` — текст кнопки создания заявки из категории
    объекта (None/пустое — текст по умолчанию «📝 Создать заявку»);
    иконка в самом тексте, к кастомному не добавляется.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📄 Получить PDF",
        callback_data=ObjectActionCB(object_id=object_id).pack(),
    )
    builder.button(
        text=request_button_text or "📝 Создать заявку",
        callback_data=CreateRequestCB(object_id=object_id).pack(),
    )
    builder.adjust(1)
    builder.row(
        types.InlineKeyboardButton(
            text="◀️ К объектам", callback_data=ObjectCB(category_id=category_id).pack()
        )
    )
    builder.row(
        types.InlineKeyboardButton(text="🏠 Главное меню", callback_data=MenuCB().pack())
    )
    return builder.as_markup()


def consent_keyboard():
    """Согласие на обработку ПД."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Согласен", callback_data=ConsentCB().pack())
    builder.button(text="❌ Отказаться", callback_data=ConsentCB(approved=False).pack())
    return builder.as_markup()


def my_requests_keyboard(items, page: int, total: int):
    """Список моих заявок с пагинацией (1 кнопка в строке)."""
    builder = InlineKeyboardBuilder()
    for req in items:
        builder.button(
            text=f"{STATUS_EMOJI.get(req.status.value, '')} Заявка #{req.id}",
            callback_data=RequestCB(request_id=req.id).pack(),
        )
    builder.adjust(1)
    _add_pager(
        builder,
        page=page,
        total=total,
        prev_cb=RequestCB(page=page - 1).pack(),
        next_cb=RequestCB(page=page + 1).pack(),
    )
    builder.row(
        types.InlineKeyboardButton(text="🏠 Главное меню", callback_data=MenuCB().pack())
    )
    return builder.as_markup()


def request_details_keyboard(request_id: int, can_cancel: bool):
    """Карточка заявки: отмена (если доступна), назад."""
    builder = InlineKeyboardBuilder()
    if can_cancel:
        builder.button(
            text="🚫 Отменить",
            callback_data=RequestCB(request_id=request_id, cancel=True).pack(),
        )
    builder.row(
        types.InlineKeyboardButton(text="◀️ Мои заявки", callback_data=RequestCB().pack())
    )
    builder.row(
        types.InlineKeyboardButton(text="🏠 Главное меню", callback_data=MenuCB().pack())
    )
    return builder.as_markup()


def points_keyboard(
    items: list,
    page: int,
    total: int,
    current_point_id: int | None = None,
) -> types.InlineKeyboardMarkup:
    """Селектор точек: кнопки с наименованием и адресом.

    ``current_point_id`` — выбранная точка (отмечается «✅»); None — не отмечать.
    Текст кнопки усекается до 64 символов (лимит Telegram).
    """
    builder = InlineKeyboardBuilder()
    for pt in items:
        text = f"{pt.name} — {pt.address}"
        if len(text) > 64:
            text = text[:61] + "…"
        if pt.id == current_point_id:
            text = f"✅ {text}"
        builder.button(
            text=text,
            callback_data=PointSelectCB(point_id=pt.id).pack(),
        )
    builder.adjust(1)
    _add_pager(
        builder,
        page=page,
        total=total,
        prev_cb=PointListCB(page=page - 1).pack(),
        next_cb=PointListCB(page=page + 1).pack(),
    )
    builder.row(
        types.InlineKeyboardButton(
            text="✖️ Отмена", callback_data=PointCancelCB().pack()
        )
    )
    return builder.as_markup()
