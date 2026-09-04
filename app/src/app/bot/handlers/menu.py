"""Хендлеры меню: категории → объекты → страница объекта → PDF."""

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.types import FSInputFile
from dishka.integrations.aiogram import FromDishka

from app.bot.keyboards import (
    CategoryCB,
    MenuCB,
    ObjectActionCB,
    ObjectCB,
    back_to_categories_keyboard,
    categories_keyboard,
    object_keyboard,
    objects_keyboard,
)
from app.bot.services import BotService
from app.services.pdf import PdfService

router = Router(name="menu")


async def ensure_visitor(callback: CallbackQuery, bot_service: BotService) -> bool:
    """Посетитель зарегистрирован и не заблокирован."""
    visitor = await bot_service.get_visitor(callback.from_user.id)
    if visitor is None:
        await callback.answer(
            "Сначала завершите регистрацию (/start)", show_alert=True
        )
        return False
    if visitor.is_blocked:
        await callback.answer("Вы заблокированы", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    """Кнопка-счётчик пагинации (N/M) — только подтверждение callback."""
    await callback.answer()


@router.callback_query(MenuCB.filter())
async def show_main_menu(
    callback: CallbackQuery,
    bot_service: FromDishka[BotService],
) -> None:
    """Главное меню: список активных категорий (первая страница)."""
    if not await ensure_visitor(callback, bot_service):
        return
    items, pages = await bot_service.list_categories(0)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "Выберите категорию:",
        reply_markup=categories_keyboard(items, 0, pages),
    )
    await callback.answer()


@router.callback_query(CategoryCB.filter(F.category_id.is_(None)))
async def show_categories(
    callback: CallbackQuery,
    callback_data: CategoryCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Список активных категорий (с пагинацией)."""
    if not await ensure_visitor(callback, bot_service):
        return
    items, pages = await bot_service.list_categories(callback_data.page)
    if not items:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "Категории пока не добавлены.",
            reply_markup=back_to_categories_keyboard(),
        )
        await callback.answer()
        return
    await callback.message.edit_text(  # type: ignore[union-attr]
        "Выберите категорию:",
        reply_markup=categories_keyboard(items, callback_data.page, pages),
    )
    await callback.answer()


@router.callback_query(CategoryCB.filter(F.category_id.is_not(None)))
async def show_objects(
    callback: CallbackQuery,
    callback_data: CategoryCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Список активных объектов категории (с пагинацией)."""
    assert callback_data.category_id is not None  # гарантировано фильтром
    if not await ensure_visitor(callback, bot_service):
        return
    items, pages = await bot_service.list_objects(
        callback_data.category_id, callback_data.page
    )
    if not items:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "В этой категории пока нет объектов.",
            reply_markup=back_to_categories_keyboard(),
        )
        await callback.answer()
        return
    await callback.message.edit_text(  # type: ignore[union-attr]
        "Выберите объект:",
        reply_markup=objects_keyboard(
            callback_data.category_id, items, callback_data.page, pages
        ),
    )
    await callback.answer()


@router.callback_query(ObjectCB.filter(F.object_id.is_not(None)))
async def show_object(
    callback: CallbackQuery,
    callback_data: ObjectCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Страница объекта: наименование, описание, PDF, заявка."""
    assert callback_data.object_id is not None  # гарантировано фильтром
    obj = await bot_service.get_object(callback_data.object_id)
    if obj is None:
        await callback.answer("Объект не найден", show_alert=True)
        return
    text = f"<b>{obj.name}</b>\n\n{obj.short_description or 'Описание отсутствует.'}"
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=object_keyboard(obj.category_id, obj.id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(ObjectActionCB.filter())
async def send_pdf(
    callback: CallbackQuery,
    callback_data: ObjectActionCB,
    bot_service: FromDishka[BotService],
    pdf_service: FromDishka[PdfService],
) -> None:
    """Отправить PDF объекта документом Telegram."""
    obj = await bot_service.get_object(callback_data.object_id)
    if obj is None or not obj.pdf_path:
        await callback.answer("PDF не загружен", show_alert=True)
        return
    try:
        path = pdf_service.open(obj.pdf_path)
    except Exception:
        await callback.answer("Файл не найден", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer_document(  # type: ignore[union-attr]
        document=FSInputFile(path),
        caption=obj.name,
    )
