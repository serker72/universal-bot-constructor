"""Хендлеры регистрации (/start, ФИО, телефон, согласие)."""

from aiogram import F, Router
from aiogram import html
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from dishka.integrations.aiogram import FromDishka

from app.bot.handlers.menu import send_categories_menu
from app.bot.handlers.points import resolve_point_flow
from app.bot.html_sanitize import sanitize_html
from app.bot.keyboards import ConsentCB, consent_keyboard
from app.bot.middlewares import BLOCKED_TEXT
from app.bot.services import BotService
from app.bot.states import RegistrationStates
from app.bot.validators import normalize_phone

router = Router(name="registration")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    dialog_manager: DialogManager,
    bot_service: FromDishka[BotService],
) -> None:
    """Точка входа: регистрация / блокировка / главное меню / выбор точки."""
    await state.clear()
    # незавершённый диалог заявки (aiogram-dialog, свой стек в Redis) —
    # сбросить, иначе следующий текст уйдёт в MessageInput старого окна
    await dialog_manager.reset_stack()
    visitor = await bot_service.get_visitor(message.from_user.id)  # type: ignore[union-attr]
    # парсинг deep link: /start point_3 → arg_point_id=3
    arg_point_id = _parse_point_arg(command.args if command else None)
    if visitor is None:
        # незарегистрирован — выбираем ФИО, потом точку
        await state.set_state(RegistrationStates.full_name)
        welcome = await bot_service.app_settings.get_welcome_text()
        prompt = "Введите ваше ФИО (полностью):"
        text = f"{sanitize_html(welcome)}\n\n{prompt}" if welcome else prompt
        await message.answer(text)
        return
    if visitor.is_blocked:
        await message.answer(BLOCKED_TEXT)
        return
    # зарегистрирован — резолвим точку
    show_selector = await resolve_point_flow(
        message, bot_service, arg_point_id, state, dialog_manager
    )
    if not show_selector:
        await _show_main_menu(message, bot_service)


def _parse_point_arg(arg: str | None) -> int | None:
    """Парсинг deep link аргумента: 'point_3' → 3.

    Возвращает None если аргумент пустой/невалидный/не относится к точкам.
    """
    if not arg:
        return None
    prefix = "point_"
    if not arg.startswith(prefix):
        return None
    try:
        return int(arg[len(prefix):])
    except ValueError:
        return None


@router.message(RegistrationStates.full_name, F.text)
async def process_full_name(
    message: Message,
    state: FSMContext,
    bot_service: FromDishka[BotService],
) -> None:
    """Шаг 1: ФИО (минимум 2 слова)."""
    full_name = (message.text or "").strip()
    if len(full_name.split()) < 2 or len(full_name) > 255:
        await message.answer("Введите ФИО полностью (минимум два слова):")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationStates.phone)
    await message.answer("Введите ваш номер телефона (например, +79001234567):")


@router.message(RegistrationStates.phone, F.text)
async def process_phone(
    message: Message,
    state: FSMContext,
    bot_service: FromDishka[BotService],
) -> None:
    """Шаг 2: телефон с контролем формата."""
    phone = normalize_phone(message.text or "")
    if phone is None:
        await message.answer(
            "Некорректный номер. Введите телефон в формате +79001234567:"
        )
        return
    await state.update_data(phone=phone)
    await state.set_state(RegistrationStates.consent)
    consent_text = await bot_service.app_settings.get_consent_text()
    await message.answer(
        sanitize_html(consent_text), reply_markup=consent_keyboard()
    )


@router.callback_query(RegistrationStates.consent, ConsentCB.filter())
async def process_consent(
    callback: CallbackQuery,
    callback_data: ConsentCB,
    state: FSMContext,
    bot_service: FromDishka[BotService],
) -> None:
    """Шаг 3: согласие — регистрация завершена или отказ."""
    if not callback_data.approved:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "Без согласия на обработку персональных данных регистрация невозможна.\n"
            "Введите /start для повторной регистрации."
        )
        await state.clear()
        await callback.answer()
        return
    data = await state.get_data()
    visitor = await bot_service.register_visitor(
        telegram_id=callback.from_user.id,
        full_name=data["full_name"],
        phone=data.get("phone"),
    )
    await state.clear()
    # сообщение с кнопкой согласия → подтверждение регистрации
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Регистрация завершена, {html.quote(visitor.full_name)}!"
    )
    await _show_main_menu(callback.message, bot_service)  # type: ignore[arg-type]
    await callback.answer()


async def _show_main_menu(message: Message, bot_service: BotService) -> None:
    """Главное меню: приветствие и список категорий отдельными сообщениями
    (меню редактируется на месте при пагинации)."""
    welcome = await bot_service.app_settings.get_welcome_text()
    if welcome:
        await message.answer(sanitize_html(welcome))
    visitor = await bot_service.get_visitor(message.from_user.id)  # type: ignore[union-attr]
    await send_categories_menu(
        message, bot_service, point_id=visitor.point_id if visitor else None
    )
