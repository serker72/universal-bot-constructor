# Образ для backend (FastAPI) и bot (aiogram) — один образ, разные command.
# Dev-зависимости (pytest и т.д.) и тесты не включаются — см. Dockerfile.test
#
# Контекст сборки — КОРЕНЬ проекта (uv.lock лежит в корне workspace):
#   docker build -t ubc-app:latest -f app/Dockerfile .
# Зависимости ставятся строго по uv.lock (uv sync --locked) — prod-образ
# совпадает с протестированным набором версий.

# --- сборка venv (multi-stage: uv и кэш не попадают в итоговый образ) ---
FROM python:3.13-slim AS build

# закреплённая версия uv (совпадает с форматом uv.lock)
COPY --from=ghcr.io/astral-sh/uv:0.7.19 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /workspace
# манифесты workspace и lock — отдельным слоем (кэш зависимостей)
COPY pyproject.toml uv.lock ./
COPY app/pyproject.toml ./app/
RUN uv sync --locked --no-dev --package ubc-app --no-install-workspace
# исходники и установка пакета (не editable — venv самодостаточен)
COPY app/src/ ./app/src/
RUN uv sync --locked --no-dev --package ubc-app --no-editable

# --- итоговый образ ---
FROM python:3.13-slim

# непривилегированный пользователь (uid совпадает с владельцем каталога
# данных на хосте; переопределяется --build-arg APP_UID=...)
ARG APP_UID=1000
RUN useradd --uid "${APP_UID}" --create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY app/src/ ./src/
COPY app/alembic.ini ./
COPY app/alembic/ ./alembic/

# Активируем venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER app

# По умолчанию запускаем backend; bot переопределяет command в compose
CMD ["uvicorn", "src.app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
