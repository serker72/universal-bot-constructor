"""Хендлеры регистрации (/start, ФИО, телефон, согласие)."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from app.bot.keyboards import ConsentCB, categories_keyboard, consent_keyboard
from app.bot.services import BotService
from app.bot.states import RegistrationStates
from app.bot.validators import normalize_phone

router = Router(name="registration")

BLOCKED_TEXT = "🚫 Вы заблокированы. Обратитесь к администрации."


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    bot_service: FromDishka[BotService],
) -> None:
    """Точка входа: регистрация / блокировка / главное меню."""
    await state.clear()
    visitor = await bot_service.get_visitor(message.from_user.id)  # type: ignore[union-attr]
    if visitor is None:
        await state.set_state(RegistrationStates.full_name)
        welcome = await bot_service.app_settings.get_welcome_text()
        await message.answer(f"{welcome}\n\nВведите ваше ФИО (полностью):")
        return
    if visitor.is_blocked:
        await message.answer(BLOCKED_TEXT)
        return
    await _show_main_menu(message, bot_service)


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
    await message.answer(consent_text, reply_markup=consent_keyboard())


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
    )
    await state.clear()
    welcome = await bot_service.app_settings.get_welcome_text()
    items, pages = await bot_service.list_categories(0)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"Регистрация завершена, {visitor.full_name}!\n"
        f"{welcome}\nВыберите категорию:",
        reply_markup=categories_keyboard(items, 0, pages),
    )
    await callback.answer()


async def _show_main_menu(message: Message, bot_service: BotService) -> None:
    """Главное меню: приветствие + список категорий."""
    welcome = await bot_service.app_settings.get_welcome_text()
    items, pages = await bot_service.list_categories(0)
    await message.answer(
        f"{welcome}\nВыберите категорию:",
        reply_markup=categories_keyboard(items, 0, pages),
    )
