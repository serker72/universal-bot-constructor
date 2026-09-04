"""Фабрики SQLAlchemy (async): движок и фабрика сессий."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Создаёт async-движок по настройкам PostgreSQL/SQLAlchemy."""
    return create_async_engine(
        settings.postgres.url,
        echo=settings.sqlalchemy.debug,
        pool_size=settings.sqlalchemy.pool_size,
        max_overflow=settings.sqlalchemy.max_overflow,
        pool_recycle=settings.sqlalchemy.pool_recycle,
        pool_pre_ping=settings.sqlalchemy.pool_pre_ping,
        pool_use_lifo=settings.sqlalchemy.pool_use_lifo,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создаёт фабрику сессий (без expire_on_commit — объекты читаются после commit)."""
    return async_sessionmaker(engine, expire_on_commit=False)
