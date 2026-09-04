"""Провайдеры сервисов."""

from dishka import Provider, Scope, provide
from faststream.rabbit import RabbitBroker
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.repository.device import DeviceRepository
from app.repository.session import SessionRepository
from app.repository.setting import SettingRepository
from app.repository.user import UserRepository
from app.services.app_settings import AppSettingsService
from app.services.auth import AuthService
from app.services.events import EventPublisher
from app.services.pdf import PdfService
from app.services.security import RateLimiter, TokenBlacklist
from app.services.tokens import TokenService


class ServiceProvider(Provider):
    """Сервисы: без состояния — APP, с сессией БД — REQUEST."""

    @provide(scope=Scope.APP)
    def provide_event_publisher(
        self, broker: RabbitBroker, settings: Settings
    ) -> EventPublisher:
        return EventPublisher(broker, settings)

    @provide(scope=Scope.APP)
    def provide_token_blacklist(self, redis: Redis) -> TokenBlacklist:
        return TokenBlacklist(redis)

    @provide(scope=Scope.APP)
    def provide_rate_limiter(self, redis: Redis) -> RateLimiter:
        return RateLimiter(redis)

    @provide(scope=Scope.APP)
    def provide_token_service(self, settings: Settings) -> TokenService:
        return TokenService(settings)

    @provide(scope=Scope.APP)
    def provide_pdf_service(self, settings: Settings) -> PdfService:
        return PdfService(settings)

    @provide(scope=Scope.REQUEST)
    def provide_app_settings(
        self, repo: SettingRepository
    ) -> AppSettingsService:
        return AppSettingsService(repo)

    @provide(scope=Scope.REQUEST)
    def provide_auth_service(
        self,
        settings: Settings,
        session: AsyncSession,
        users: UserRepository,
        devices: DeviceRepository,
        sessions: SessionRepository,
        tokens: TokenService,
        blacklist: TokenBlacklist,
    ) -> AuthService:
        return AuthService(
            settings=settings,
            session=session,
            users=users,
            devices=devices,
            sessions=sessions,
            tokens=tokens,
            blacklist=blacklist,
        )
