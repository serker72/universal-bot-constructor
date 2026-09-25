"""Middleware бота.

- UpdateContainerMiddleware (outer, после dishka) — запоминает DI-контейнер
  текущего обновления в contextvar;
- CommitBeforeTelegramMiddleware (request-middleware сессии Bot) — перед
  каждым вызовом Telegram API фиксирует транзакцию БД текущего обновления:
  при pool_mode=transaction pgbouncer не держит серверное соединение на время
  сетевого I/O с Telegram (commit в финализаторе был бы уже после ответа);
- BlockedVisitorMiddleware (outer) — заблокированный посетитель не может
  пользоваться меню (в т.ч. по старым кнопкам): карточка объекта, PDF, заявки.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware,
    NextRequestMiddlewareType,
)
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response, TelegramType
from aiogram.types import CallbackQuery, Message, TelegramObject
from dishka import AsyncContainer
from dishka.integrations.aiogram import CONTAINER_NAME
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services import BotService

BLOCKED_TEXT = "🚫 Вы заблокированы. Обратитесь к администрации."

# DI-контейнер обрабатываемого обновления (None — вне обновления, например
# рассылка уведомлений консьюмером RabbitMQ)
_update_container: ContextVar[AsyncContainer | None] = ContextVar(
    "ubc_update_container", default=None
)


class UpdateContainerMiddleware(BaseMiddleware):
    """Сохраняет REQUEST-контейнер dishka обновления в contextvar."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        token = _update_container.set(data.get(CONTAINER_NAME))
        try:
            return await handler(event, data)
        finally:
            _update_container.reset(token)


class CommitBeforeTelegramMiddleware(BaseRequestMiddleware):
    """Commit транзакции БД обновления перед запросом к Telegram API."""

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        container = _update_container.get()
        if container is not None:
            session = await container.get(AsyncSession)
            if session.in_transaction():
                await session.commit()
        return await make_request(bot, method)


class BlockedVisitorMiddleware(BaseMiddleware):
    """Отсекает обновления заблокированного посетителя (кроме /start)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        container: AsyncContainer | None = data.get(CONTAINER_NAME)
        if user is None or container is None:
            return await handler(event, data)
        if isinstance(event, Message) and (event.text or "").startswith("/start"):
            # /start сам сообщает о блокировке (registration.cmd_start)
            return await handler(event, data)
        service = await container.get(BotService)
        visitor = await service.get_visitor(user.id)
        if visitor is not None and visitor.is_blocked:
            if isinstance(event, CallbackQuery):
                await event.answer("Вы заблокированы", show_alert=True)
            elif isinstance(event, Message):
                await event.answer(BLOCKED_TEXT)
            return None
        return await handler(event, data)
