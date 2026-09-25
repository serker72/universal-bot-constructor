"""Провайдеры бота: Bot (aiogram) и BotService."""

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services import BotService
from app.config.settings import Settings
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository
from app.repository.request import RequestRepository
from app.repository.request_field import RequestFieldRepository
from app.repository.visitor import VisitorRepository
from app.services.app_settings import AppSettingsService
from app.services.events import EventPublisher


class BotProvider(Provider):
    """Bot — синглтон (APP), BotService — на обновление (REQUEST)."""

    @provide(scope=Scope.APP)
    def provide_bot(self, settings: Settings) -> Bot:
        session = (
            AiohttpSession(proxy=settings.bot.proxy_url)
            if settings.bot.proxy_url
            else AiohttpSession()
        )
        # parse_mode=HTML по умолчанию: тексты (приветствие, согласие, карточка
        # объекта) — санитизированный HTML; пользовательские данные всегда
        # экранируются (html.quote)
        return Bot(
            token=settings.bot.token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    @provide(scope=Scope.REQUEST)
    def provide_bot_service(
        self,
        session: AsyncSession,
        visitors: VisitorRepository,
        categories: CategoryRepository,
        objects: ObjectRepository,
        requests: RequestRepository,
        request_fields: RequestFieldRepository,
        app_settings: AppSettingsService,
        publisher: EventPublisher,
    ) -> BotService:
        return BotService(
            session=session,
            visitors=visitors,
            categories=categories,
            objects=objects,
            requests=requests,
            request_fields=request_fields,
            app_settings=app_settings,
            publisher=publisher,
        )
