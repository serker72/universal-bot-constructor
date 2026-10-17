"""Хендлеры выбора точки продаж (филиала)."""

from aiogram import F, Router
from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from dishka.integrations.aiogram import FromDishka

from app.bot.handlers.menu import send_categories_menu
from app.bot.keyboards import (
    ChangePointCB,
    PointCancelCB,
    PointListCB,
    PointSelectCB,
    points_keyboard,
)
from app.bot.services import BotService
from app.bot.states import PointStates

router = Router(name="points")


@router.callback_query(ChangePointCB.filter())
async def show_change_point_selector(
    callback: CallbackQuery,
    callback_data: ChangePointCB,
    bot_service: FromDishka[BotService],
    state: FSMContext,
    dialog_manager: DialogManager,
) -> None:
    """Кнопка «Сменить филиал» — показ селектора с текущей точкой."""
    if not await _ensure_visitor_and_reset(callback, bot_service, dialog_manager):
        return
    await state.set_state(PointStates.choose)
    await _show_selector(callback, bot_service, state, dialog_manager, page=0)
    await callback.answer()


@router.callback_query(PointListCB.filter())
async def show_point_selector_page(
    callback: CallbackQuery,
    callback_data: PointListCB,
    bot_service: FromDishka[BotService],
    state: FSMContext,
    dialog_manager: DialogManager,
) -> None:
    """Пагинация селектора точек."""
    if not await _ensure_visitor_and_reset(callback, bot_service, dialog_manager):
        return
    await _show_selector(callback, bot_service, state, dialog_manager, page=callback_data.page)
    await callback.answer()


@router.callback_query(PointSelectCB.filter())
async def select_point(
    callback: CallbackQuery,
    callback_data: PointSelectCB,
    bot_service: FromDishka[BotService],
    state: FSMContext,
    dialog_manager: DialogManager,
) -> None:
    """Выбор точки: валидация, сохранение, переход в меню."""
    if not await _ensure_visitor_and_reset(callback, bot_service, dialog_manager):
        return
    point = await bot_service.get_active_point(callback_data.point_id)
    if point is None:
        await callback.answer("Филиал не найден или неактивен", show_alert=True)
        return
    await bot_service.set_visitor_point(callback.from_user.id, point.id)
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Филиал «{html.quote(point.name)}» выбран."
    )
    # после выбора точки — главное меню (категории)
    await send_categories_menu(
        callback.message, bot_service, edit=True, point_id=point.id  # type: ignore[arg-type]
    )
    await callback.answer()


@router.callback_query(PointCancelCB.filter())
async def cancel_point_selection(
    callback: CallbackQuery,
    callback_data: PointCancelCB,
    bot_service: FromDishka[BotService],
    state: FSMContext,
    dialog_manager: DialogManager,
) -> None:
    """Отмена выбора точки — возврат в меню (без смены point_id)."""
    await state.clear()
    await callback.answer("Выбор точки отменён.")


async def _ensure_visitor_and_reset(
    callback: CallbackQuery,
    bot_service: BotService,
    dialog_manager: DialogManager,
) -> bool:
    """Проверка посетителя + сброс диалога заявки."""
    visitor = await bot_service.get_visitor(callback.from_user.id)
    if visitor is None:
        await callback.answer(
            "Сначала завершите регистрацию (/start)", show_alert=True
        )
        return False
    if visitor.is_blocked:
        await callback.answer("Вы заблокированы", show_alert=True)
        return False
    # незавершённый диалог заявки — сбросить (иначе текст уйдёт в старое окно)
    await dialog_manager.reset_stack()
    return True


async def _show_selector(
    callback: CallbackQuery,
    bot_service: BotService,
    state: FSMContext,
    dialog_manager: DialogManager,
    *,
    page: int,
) -> None:
    """Показать/отредактировать сообщение селектора точек."""
    items, pages, page = await bot_service.list_active_points(page)
    visitor = await bot_service.get_visitor(callback.from_user.id)  # type: ignore[assignment]
    current_id = visitor.point_id if visitor is not None else None
    if not items:
        await callback.message.edit_text("Филиалы пока не добавлены.")  # type: ignore[union-attr]
        return
    await callback.message.edit_text(  # type: ignore[union-attr]
        "Выберите филиал:",
        reply_markup=points_keyboard(items, page, pages, current_id),
    )


async def resolve_point_flow(
    message: Message,
    bot_service: BotService,
    arg_point_id: int | None,
    state: FSMContext,
    dialog_manager: DialogManager,
    *,
    edit: bool = True,
) -> bool:
    """Резолв сценария выбора точки по правилу из плана.

    Возвращает True если нужно показать селектор (сценарий вызван
    через _show_selector), False если можно сразу показать меню.
    """
    count = await bot_service.count_active_points()
    if count == 0:
        # нет точек — работаем без фильтрации (обратная совместимость)
        return False
    if count == 1:
        # одна точка — автофиксация
        points, _, _ = await bot_service.list_active_points(0)
        only = points[0]
        await bot_service.set_visitor_point(message.from_user.id, only.id)  # type: ignore[union-attr]
        return False
    # несколько точек
    if arg_point_id is not None:
        # аргумент передан — валидируем и сохраняем
        point = await bot_service.get_active_point(arg_point_id)
        if point is not None:
            await bot_service.set_visitor_point(
                message.from_user.id, point.id  # type: ignore[arg-type]
            )
            return False
    # нет валидного аргумента — показываем селектор
    await _show_selector_for_message(
        message, bot_service, state, dialog_manager, page=0
    )
    return True


async def _show_selector_for_message(
    message: Message,
    bot_service: BotService,
    state: FSMContext,
    dialog_manager: DialogManager,
    *,
    page: int,
) -> None:
    """Показать селектор точек как новое сообщение (для /start)."""
    items, pages, page = await bot_service.list_active_points(page)
    visitor = await bot_service.get_visitor(message.from_user.id)  # type: ignore[assignment]
    current_id = visitor.point_id if visitor is not None else None
    await state.set_state(PointStates.choose)
    await message.answer(
        "Выберите филиал:",
        reply_markup=points_keyboard(items, page, pages, current_id),
    )
    await dialog_manager.reset_stack()
