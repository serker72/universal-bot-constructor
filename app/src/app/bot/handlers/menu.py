"""Хендлеры меню: категории → объекты → страница объекта → PDF.

Заблокированные посетители отсекаются BlockedVisitorMiddleware (в т.ч. по
старым кнопкам); ensure_visitor дополнительно требует завершённой регистрации.
"""

from aiogram import F, Router
from aiogram import html
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile, Message
from dishka.integrations.aiogram import FromDishka

from app.bot.html_sanitize import sanitize_html
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
from app.domain.models import Visitor
from app.log import get_logger
from app.services.pdf import PdfError, PdfService

router = Router(name="menu")

log = get_logger(__name__)

CATEGORIES_TEXT = "Выберите категорию:"


async def ensure_visitor(
    callback: CallbackQuery, bot_service: BotService
) -> Visitor | None:
    """Посетитель зарегистрирован и не заблокирован (иначе — alert и None)."""
    visitor = await bot_service.get_visitor(callback.from_user.id)
    if visitor is None:
        await callback.answer(
            "Сначала завершите регистрацию (/start)", show_alert=True
        )
        return None
    if visitor.is_blocked:
        await callback.answer("Вы заблокированы", show_alert=True)
        return None
    return visitor


async def send_categories_menu(
    message: Message, bot_service: BotService, *, page: int = 0, edit: bool = False
) -> None:
    """Меню категорий (страница page): новое сообщение или правка текущего."""
    items, pages, page = await bot_service.list_categories(page)
    if not items:
        text, markup = "Категории пока не добавлены.", back_to_categories_keyboard()
    else:
        text, markup = CATEGORIES_TEXT, categories_keyboard(items, page, pages)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _show_objects_page(
    callback: CallbackQuery, bot_service: BotService, category_id: int, page: int
) -> None:
    """Страница объектов категории (общая для выбора категории и «К объектам»)."""
    if not await ensure_visitor(callback, bot_service):
        return
    items, pages, page = await bot_service.list_objects(category_id, page)
    if not items:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "В этой категории пока нет объектов.",
            reply_markup=back_to_categories_keyboard(),
        )
    else:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "Выберите объект:",
            reply_markup=objects_keyboard(category_id, items, page, pages),
        )
    await callback.answer()


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
    await send_categories_menu(callback.message, bot_service, edit=True)  # type: ignore[arg-type]
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
    await send_categories_menu(
        callback.message,  # type: ignore[arg-type]
        bot_service,
        page=callback_data.page,
        edit=True,
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
    await _show_objects_page(
        callback, bot_service, callback_data.category_id, callback_data.page
    )


@router.callback_query(ObjectCB.filter(F.object_id.is_(None)))
async def back_to_objects(
    callback: CallbackQuery,
    callback_data: ObjectCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Кнопка «К объектам»: список объектов категории (с пагинацией)."""
    await _show_objects_page(
        callback, bot_service, callback_data.category_id, callback_data.page
    )


@router.callback_query(ObjectCB.filter(F.object_id.is_not(None)))
async def show_object(
    callback: CallbackQuery,
    callback_data: ObjectCB,
    bot_service: FromDishka[BotService],
) -> None:
    """Страница объекта: наименование, описание, PDF, заявка."""
    assert callback_data.object_id is not None  # гарантировано фильтром
    if not await ensure_visitor(callback, bot_service):
        return
    obj = await bot_service.get_object(callback_data.object_id)
    if obj is None:
        await callback.answer("Объект не найден", show_alert=True)
        return
    text = (
        f"<b>{html.quote(obj.name)}</b>\n\n"
        f"{sanitize_html(obj.short_description) or 'Описание отсутствует.'}"
    )
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=object_keyboard(
                obj.category_id,
                obj.id,
                request_button_text=obj.category.button_text,
            ),
        )
    except TelegramBadRequest:
        # описание не прошло проверку Telegram (длина/разметка) — карточка
        # без описания вместо «вечного» индикатора загрузки
        log.warning("object_card_render_failed", object_id=obj.id)
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"<b>{html.quote(obj.name)}</b>",
            reply_markup=object_keyboard(
                obj.category_id,
                obj.id,
                request_button_text=obj.category.button_text,
            ),
        )
    await callback.answer()


@router.callback_query(ObjectActionCB.filter())
async def send_pdf(
    callback: CallbackQuery,
    callback_data: ObjectActionCB,
    bot_service: FromDishka[BotService],
    pdf_service: FromDishka[PdfService],
) -> None:
    """Отправить PDF объекта документом Telegram.

    Повторная отправка — по сохранённому file_id (без загрузки файла заново);
    file_id сбрасывается при замене PDF.
    """
    if not await ensure_visitor(callback, bot_service):
        return
    obj = await bot_service.get_object(callback_data.object_id)
    if obj is None or not obj.pdf_path:
        await callback.answer("PDF не загружен", show_alert=True)
        return
    await callback.answer()
    if obj.telegram_file_id:
        try:
            await callback.message.answer_document(  # type: ignore[union-attr]
                document=obj.telegram_file_id,
                caption=html.quote(obj.name),
            )
            return
        except TelegramBadRequest:
            # file_id устарел — отправляем файл заново
            log.warning("pdf_file_id_invalid", object_id=obj.id)
    try:
        path = pdf_service.open(obj.pdf_path)
    except PdfError:
        await callback.message.answer("Файл не найден")  # type: ignore[union-attr]
        return
    sent = await callback.message.answer_document(  # type: ignore[union-attr]
        document=FSInputFile(path),
        caption=html.quote(obj.name),
    )
    if sent.document is not None:
        await bot_service.save_pdf_file_id(obj.id, obj.pdf_path, sent.document.file_id)
