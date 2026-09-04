"""Точка входа бота (aiogram).

Запуск в контейнере: python -m src.app.bot.main

Режимы:
- long-polling (dev/loc, по умолчанию);
- webhook (prod, если задан BOT_WEBHOOK_BASE_URL; запросы проксирует nginx).

Вместе с ботом в этом же процессе работают консьюмеры RabbitMQ
(уведомления админам и менеджерам, см. app.bot.notifications).
"""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from dishka.integrations.aiogram import setup_dishka
from faststream.rabbit import RabbitBroker

from app.bot.handlers import menu, registration, requests
from app.bot.notifications import register_notification_consumers
from app.config.settings import Settings
from app.di import build_container
from app.log import get_logger, setup_logging

logger = get_logger(__name__)


async def _run_webhook(settings: Settings, bot: Bot, dp: Dispatcher) -> None:
    """Prod: aiohttp-приложение, принимающее апдейты webhook от nginx."""
    from aiogram.webhook.aiohttp_server import (
        SimpleRequestHandler,
        setup_application,
    )
    from aiohttp import web

    url = settings.bot.webhook_base_url.rstrip("/") + settings.bot.webhook_path
    secret = settings.bot.webhook_secret or None
    await bot.set_webhook(url, secret_token=secret, drop_pending_updates=True)
    logger.info("webhook_set", url=url)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(
        app, path=settings.bot.webhook_path
    )
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.bot.webhook_host, port=settings.bot.webhook_port)
    await site.start()
    logger.info(
        "bot_webhook_listening",
        host=settings.bot.webhook_host,
        port=settings.bot.webhook_port,
    )
    await asyncio.Event().wait()  # работать до остановки процесса


async def run() -> None:
    """Собрать и запустить бота: DI, FSM (Redis), роутеры, консьюмеры."""
    settings = Settings()
    setup_logging(debug=settings.project.environment != "prod")

    container = build_container()
    try:
        # 1. Подписчики ДО старта брокера (иначе очереди не создаются)
        broker = await container.get(RabbitBroker)  # без start (см. di/broker.py)
        register_notification_consumers(broker, container, settings)
        await broker.start()

        # 2. Bot, dispatcher, роутеры
        bot = await container.get(Bot)

        dp = Dispatcher(
            storage=RedisStorage.from_url(
                settings.redis.url,
                key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
            )
        )
        dp.include_router(registration.router)
        dp.include_router(menu.router)
        dp.include_router(requests.router)
        # auto_inject=True — обернуть хендлеры inject'ом (FromDishka-параметры)
        setup_dishka(container, dp, auto_inject=True)

        if settings.bot.webhook_base_url:
            await _run_webhook(settings, bot, dp)
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("bot_started_polling")
            await dp.start_polling(bot)
    finally:
        await container.close()


def main() -> None:
    """Точка входа: python -m src.app.bot.main."""
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("bot_stopped")


if __name__ == "__main__":
    main()
