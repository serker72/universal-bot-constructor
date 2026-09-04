"""Провайдеры репозиториев (сессия — на запрос)."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.category import CategoryRepository
from app.repository.device import DeviceRepository
from app.repository.object import ObjectRepository
from app.repository.request import RequestRepository
from app.repository.session import SessionRepository
from app.repository.setting import SettingRepository
from app.repository.user import UserRepository
from app.repository.visitor import VisitorRepository


class RepositoryProvider(Provider):
    """Все репозитории живут в области запроса и разделяют одну сессию."""

    @provide(scope=Scope.REQUEST)
    def provide_category_repo(self, session: AsyncSession) -> CategoryRepository:
        return CategoryRepository(session)

    @provide(scope=Scope.REQUEST)
    def provide_object_repo(self, session: AsyncSession) -> ObjectRepository:
        return ObjectRepository(session)

    @provide(scope=Scope.REQUEST)
    def provide_user_repo(self, session: AsyncSession) -> UserRepository:
        return UserRepository(session)

    @provide(scope=Scope.REQUEST)
    def provide_visitor_repo(self, session: AsyncSession) -> VisitorRepository:
        return VisitorRepository(session)

    @provide(scope=Scope.REQUEST)
    def provide_request_repo(self, session: AsyncSession) -> RequestRepository:
        return RequestRepository(session)

    @provide(scope=Scope.REQUEST)
    def provide_device_repo(self, session: AsyncSession) -> DeviceRepository:
        return DeviceRepository(session)

    @provide(scope=Scope.REQUEST)
    def provide_session_repo(self, session: AsyncSession) -> SessionRepository:
        return SessionRepository(session)

    @provide(scope=Scope.REQUEST)
    def provide_setting_repo(self, session: AsyncSession) -> SettingRepository:
        return SettingRepository(session)
