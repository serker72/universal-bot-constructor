"""Хендлеры заявок: создание (динамический диалог), мои заявки, отмена."""

from aiogram import F, Router
from aiogram import html
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode
from dishka.integrations.aiogram import FromDishka

from app.bot.keyboards import (
    CreateRequestCB,
    RequestCB,
    back_to_categories_keyboard,
    my_requests_keyboard,
    request_details_keyboard,
)
from app.bot.services import BotService, BotServiceError
from app.bot.states import DynamicRequestSG
from app.bot.statuses import STATUS_TEXT
from app.bot.handlers.menu import ensure_visitor

router = Router(name="requests")


# -- создание заявки (динамический конструктор, aiogram-dialog) ---------------


@router.callback_query(CreateRequestCB.filter())
async def start_request(
    callback: CallbackQuery,
    callback_data: CreateRequestCB,
    dialog_manager: DialogManager,
    bot_service: FromDishka[BotService],
) -> None:
    """Кнопка «Создать заявку»: запуск диалога по схеме полей категории."""
    if not await ensure_visitor(callback, bot_service):
        return
    # схема полей заявки для категории объекта (сортировка из БД)
    try:
        schema = await bot_service.get_category_schema(callback_data.object_id)
    except BotServiceError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    # RESET_STACK: закрыть возможный незавершённый диалог (состояние
    # хранится в Redis и переживает рестарты), иначе он останется в стеке
    # и отрисуется после done() нового диалога.
    await dialog_manager.start(
        DynamicRequestSG.input_phone,
        mode=StartMode.RESET_STACK,
        data={
            "object_id": callback_data.object_id,
            "schema": schema,
            "answers": {},
        },
    )
    # снять индикатор загрузки с кнопки
    await callback.answer()


# -- мои заявки --------------------------------------------------------------


@router.callback_query(RequestCB.filter(F.request_id.is_(None)))
async def show_my_requests(
    callback: CallbackQuery,
    callback_data: RequestCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Список заявок посетителя (с пагинацией)."""
    visitor = await ensure_visitor(callback, bot_service)
    if visitor is None:
        return
    items, pages, page = await bot_service.list_visitor_requests(
        visitor.id, page=callback_data.page
    )
    if not items:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "У вас пока нет заявок.", reply_markup=back_to_categories_keyboard()
        )
        await callback.answer()
        return
    await callback.message.edit_text(  # type: ignore[union-attr]
        "Ваши заявки:",
        reply_markup=my_requests_keyboard(items, page, pages),
    )
    await callback.answer()


@router.callback_query(RequestCB.filter(F.cancel.is_(True)))
async def cancel_request(
    callback: CallbackQuery,
    callback_data: RequestCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Отмена заявки (new — всегда, approved — в пределах интервала)."""
    visitor = await ensure_visitor(callback, bot_service)
    if visitor is None:
        return
    # блокировка строки: параллельная смена статуса менеджером не перезаписывается
    req = await bot_service.get_request(
        callback_data.request_id, visitor.id, for_update=True  # type: ignore[arg-type]
    )
    if req is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    try:
        await bot_service.cancel_request(req)
    except BotServiceError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("Заявка отменена")
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"🚫 Заявка #{req.id} отменена.",
        reply_markup=back_to_categories_keyboard(),
    )


@router.callback_query(RequestCB.filter(F.cancel.is_(False) & F.request_id.is_not(None)))
async def show_request_details(
    callback: CallbackQuery,
    callback_data: RequestCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Карточка заявки: статус, телефон, значения полей, кнопка отмены."""
    visitor = await ensure_visitor(callback, bot_service)
    if visitor is None:
        return
    req = await bot_service.get_request(callback_data.request_id, visitor.id)  # type: ignore[arg-type]
    if req is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    status = req.status.value
    text = (
        f"Заявка #{req.id}\n"
        f"Статус: {STATUS_TEXT.get(status, status)}\n"
        f"Телефон: {html.quote(req.phone)}"
    )
    # значения динамических полей заявки (label: value); parse_mode=HTML —
    # пользовательский ввод экранируется
    for label, value in await bot_service.get_request_values(req.id):
        text += f"\n{html.quote(label)}: {html.quote(value) if value else '—'}"
    can_cancel = await bot_service.can_cancel(req)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text, reply_markup=request_details_keyboard(req.id, can_cancel)
    )
    await callback.answer()
