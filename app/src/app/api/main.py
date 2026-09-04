"""Точка входа backend (FastAPI).

Собирает приложение: логирование, DI-контейнер (dishka),
CORS, роутеры. Команда запуска в контейнере:
uvicorn src.app.api.main:app
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from faststream.rabbit import RabbitBroker

from app.api.health import router as health_router
from app.api.routers import (
    auth_router,
    categories_router,
    devices_router,
    objects_router,
    pdf_router,
    requests_router,
    sessions_router,
    settings_router,
    users_router,
    visitors_router,
)
from app.config.settings import settings
from app.di import build_container
from app.log import setup_logging
from dishka.integrations.fastapi import setup_dishka


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Старт/остановка брокера (публикация событий из API)."""
    broker: RabbitBroker = await app.state.dishka_container.get(RabbitBroker)
    await broker.start()
    yield
    await broker.stop()


def create_app() -> FastAPI:
    """Фабрика приложения."""
    setup_logging(debug=settings.backend.debug)

    container = build_container()
    app = FastAPI(
        title="Universal Bot Constructor API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # DI: контейнер доступен через app.state.dishka_container
    setup_dishka(container, app=app)
    app.state.dishka_container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=settings.backend.api_prefix)
    app.include_router(auth_router, prefix=settings.backend.api_prefix)
    app.include_router(categories_router, prefix=settings.backend.api_prefix)
    app.include_router(objects_router, prefix=settings.backend.api_prefix)
    app.include_router(pdf_router, prefix=settings.backend.api_prefix)
    app.include_router(users_router, prefix=settings.backend.api_prefix)
    app.include_router(visitors_router, prefix=settings.backend.api_prefix)
    app.include_router(requests_router, prefix=settings.backend.api_prefix)
    app.include_router(devices_router, prefix=settings.backend.api_prefix)
    app.include_router(sessions_router, prefix=settings.backend.api_prefix)
    app.include_router(settings_router, prefix=settings.backend.api_prefix)

    return app


app = create_app()
