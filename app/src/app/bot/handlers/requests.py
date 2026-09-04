"""Хендлеры заявок: создание, мои заявки, отмена."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from app.bot.keyboards import (
    CreateRequestCB,
    RequestCB,
    back_to_categories_keyboard,
    my_requests_keyboard,
    request_details_keyboard,
)
from app.bot.services import BotService, BotServiceError
from app.bot.states import RequestStates
from app.bot.validators import normalize_phone

router = Router(name="requests")

STATUS_TEXT = {
    "new": "🆕 Новая",
    "approved": "✅ Подтверждена",
    "rejected": "❌ Отклонена",
    "completed": "🏁 Выполнена",
    "cancelled_by_customer": "🚫 Отменена вами",
}


# -- создание заявки --------------------------------------------------------


@router.callback_query(CreateRequestCB.filter())
async def start_request(
    callback: CallbackQuery,
    callback_data: CreateRequestCB,
    state: FSMContext,
    bot_service: FromDishka[BotService],
) -> None:
    """Кнопка «Создать заявку» на странице объекта."""
    visitor = await bot_service.get_visitor(callback.from_user.id)
    if visitor is None:
        await callback.answer("Сначала завершите регистрацию (/start)", show_alert=True)
        return
    if visitor.is_blocked:
        await callback.answer("Вы заблокированы", show_alert=True)
        return
    await state.set_state(RequestStates.phone)
    await state.update_data(object_id=callback_data.object_id)
    await callback.message.answer(  # type: ignore[union-attr]
        "Введите ваш номер телефона (например, +79001234567):"
    )
    await callback.answer()


@router.message(RequestStates.phone, F.text)
async def process_request_phone(
    message: Message,
    state: FSMContext,
    bot_service: FromDishka[BotService],
) -> None:
    """Шаг 1: телефон с контролем формата."""
    phone = normalize_phone(message.text or "")
    if phone is None:
        await message.answer(
            "Некорректный номер. Введите телефон в формате +79001234567:"
        )
        return
    await state.update_data(phone=phone)
    await state.set_state(RequestStates.comment)
    await message.answer(
        "Добавьте комментарий к заявке (или отправьте «-» чтобы пропустить):"
    )


@router.message(RequestStates.comment, F.text)
async def process_request_comment(
    message: Message,
    state: FSMContext,
    bot_service: FromDishka[BotService],
) -> None:
    """Шаг 2: комментарий (или «-») → создание заявки."""
    data = await state.get_data()
    comment = (message.text or "").strip()
    comment = None if comment in ("-", "") else comment
    visitor = await bot_service.get_visitor(message.from_user.id)  # type: ignore[union-attr]
    if visitor is None:
        await message.answer("Сначала завершите регистрацию (/start).")
        await state.clear()
        return
    try:
        req = await bot_service.create_request(
            visitor=visitor,
            object_id=int(data["object_id"]),
            phone=data["phone"],
            comment=comment,
        )
    except BotServiceError as exc:
        await message.answer(
            f"Ошибка: {exc}", reply_markup=back_to_categories_keyboard()
        )
        await state.clear()
        return
    await state.clear()
    await message.answer(
        f"✅ Заявка #{req.id} создана. Менеджер свяжется с вами.",
        reply_markup=back_to_categories_keyboard(),
    )


# -- мои заявки --------------------------------------------------------------


@router.callback_query(RequestCB.filter(F.request_id.is_(None)))
async def show_my_requests(
    callback: CallbackQuery,
    callback_data: RequestCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Список заявок посетителя (с пагинацией)."""
    visitor = await bot_service.get_visitor(callback.from_user.id)
    if visitor is None:
        await callback.answer("Сначала завершите регистрацию (/start)", show_alert=True)
        return
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
    visitor = await bot_service.get_visitor(callback.from_user.id)
    if visitor is None:
        await callback.answer("Нет доступа", show_alert=True)
        return
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
    visitor = await bot_service.get_visitor(callback.from_user.id)
    if visitor is None:
        await callback.answer("Нет доступа", show_alert=True)
        return
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
    if req.comment:
        text += f"\nКомментарий: {req.comment}"
    can_cancel = await bot_service.can_cancel(req)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text, reply_markup=request_details_keyboard(req.id, can_cancel)
    )
    await callback.answer()
