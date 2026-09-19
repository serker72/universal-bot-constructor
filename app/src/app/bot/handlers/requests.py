"""Хендлеры заявок: создание (диалог), мои заявки, отмена."""

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode
from dishka.integrations.aiogram import FromDishka

from app.bot.dialogs.request_dialog import FLAG_USE_END_DATE, FLAG_USE_TIME
from app.bot.keyboards import (
    CreateRequestCB,
    RequestCB,
    back_to_categories_keyboard,
    my_requests_keyboard,
    request_details_keyboard,
)
from app.bot.services import BotService, BotServiceError
from app.bot.states import RequestStates
from app.bot.statuses import STATUS_TEXT
from app.bot.handlers.menu import ensure_visitor

router = Router(name="requests")


# -- создание заявки (диалог aiogram-dialog) ---------------------------------


@router.callback_query(CreateRequestCB.filter())
async def start_request(
    callback: CallbackQuery,
    callback_data: CreateRequestCB,
    dialog_manager: DialogManager,
    bot_service: FromDishka[BotService],
) -> None:
    """Кнопка «Создать заявку»: запуск диалога с флагами из настроек."""
    if not await ensure_visitor(callback, bot_service):
        return
    use_time = await bot_service.app_settings.get_is_use_time_in_request()
    use_end_date = await bot_service.app_settings.get_is_use_end_date_in_request()
    # RESET_STACK: закрыть возможный незавершённый диалог (состояние
    # хранится в Redis и переживает рестарты), иначе он останется в стеке
    # и отрисуется после done() нового диалога.
    await dialog_manager.start(
        RequestStates.input_phone,
        mode=StartMode.RESET_STACK,
        data={
            "object_id": callback_data.object_id,
            FLAG_USE_TIME: use_time,
            FLAG_USE_END_DATE: use_end_date,
        },
    )


# -- мои заявки --------------------------------------------------------------


@router.callback_query(RequestCB.filter(F.request_id.is_(None)))
async def show_my_requests(
    callback: CallbackQuery,
    callback_data: RequestCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Список заявок посетителя (с пагинацией)."""
    if not await ensure_visitor(callback, bot_service):
        return
    visitor = await bot_service.get_visitor(callback.from_user.id)
    items, pages = await bot_service.list_visitor_requests(
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
        reply_markup=my_requests_keyboard(items, callback_data.page, pages),
    )
    await callback.answer()


@router.callback_query(RequestCB.filter(F.cancel.is_(True)))
async def cancel_request(
    callback: CallbackQuery,
    callback_data: RequestCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Отмена заявки (new — всегда, approved — в пределах интервала)."""
    if not await ensure_visitor(callback, bot_service):
        return
    visitor = await bot_service.get_visitor(callback.from_user.id)
    req = await bot_service.get_request(callback_data.request_id, visitor.id)  # type: ignore[arg-type]
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
    """Карточка заявки: статус, телефон, комментарий, кнопка отмены."""
    if not await ensure_visitor(callback, bot_service):
        return
    visitor = await bot_service.get_visitor(callback.from_user.id)
    req = await bot_service.get_request(callback_data.request_id, visitor.id)  # type: ignore[arg-type]
    if req is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    status = req.status.value
    text = (
        f"Заявка #{req.id}\n"
        f"Статус: {STATUS_TEXT.get(status, status)}\n"
        f"Телефон: {req.phone}"
    )
    if req.start_date:
        start = req.start_date.strftime("%d.%m.%Y")
        if req.start_time:
            start += f" {req.start_time.strftime('%H:%M')}"
        text += f"\nНачало: {start}"
    if req.end_date:
        end = req.end_date.strftime("%d.%m.%Y")
        if req.end_time:
            end += f" {req.end_time.strftime('%H:%M')}"
        text += f"\nОкончание: {end}"
    if req.comment:
        text += f"\nКомментарий: {req.comment}"
    can_cancel = await bot_service.can_cancel(req)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text, reply_markup=request_details_keyboard(req.id, can_cancel)
    )
    await callback.answer()
