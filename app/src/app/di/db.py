"""Провайдеры БД: движок, фабрика сессий, сессия запроса."""

from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config.settings import Settings
from app.db.engine import create_engine, create_session_factory


class DbProvider(Provider):
    """Движок и фабрика сессий — синглтоны, сессия — на запрос."""

    @provide(scope=Scope.APP)
    async def provide_engine(self, settings: Settings) -> AsyncIterator[AsyncEngine]:
        """Движок; при закрытии контейнера — dispose (пул соединений закрывается)."""
        engine = create_engine(settings)
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    def provide_session_factory(
        self, engine: AsyncEngine
    ) -> async_sessionmaker[AsyncSession]:
        return create_session_factory(engine)

    @provide(scope=Scope.REQUEST)
    async def provide_session(
        self, factory: async_sessionmaker[AsyncSession]
    ) -> AsyncIterator[AsyncSession]:
        """Сессия на запрос: commit при успехе, rollback при ошибке.

        Финализатор — страховка: API коммитит до ответа (TransactionalRoute),
        бот — до вызовов Telegram (CommitMiddleware). Здесь commit фиксирует
        только то, что изменилось после них (обычно ничего).
        """
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
