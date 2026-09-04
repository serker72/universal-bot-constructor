"""Провайдеры зависимостей (dishka) и сборка контейнера."""

from dishka import AsyncContainer, Provider, make_async_container
from dishka.integrations.fastapi import FastapiProvider

from app.api.deps import AuthProvider
from app.di.bot import BotProvider
from app.di.broker import BrokerProvider
from app.di.db import DbProvider
from app.di.redis import RedisProvider
from app.di.repository import RepositoryProvider
from app.di.service import ServiceProvider
from app.di.settings import SettingsProvider


def get_providers() -> list[Provider]:
    """Все провайдеры приложения."""
    return [
        SettingsProvider(),
        FastapiProvider(),  # Request из контекста FastAPI
        DbProvider(),
        RedisProvider(),
        BrokerProvider(),
        RepositoryProvider(),
        ServiceProvider(),
        AuthProvider(),
        BotProvider(),
    ]


def build_container() -> AsyncContainer:
    """Собрать корневой DI-контейнер приложения."""
    return make_async_container(*get_providers())
