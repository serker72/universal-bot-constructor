# Образ для backend (FastAPI) и bot (aiogram) — один образ, разные command
FROM python:3.13-slim

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Копируем исходники и зависимости, затем ставим пакет (editable):
# важно скопировать src/ ДО установки — иначе setuptools не найдёт пакет
COPY pyproject.toml ./
COPY src/ ./src/
COPY alembic.ini* ./
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

# Активируем venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# По умолчанию запускаем backend; bot переопределяет command в compose
CMD ["uvicorn", "src.app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
