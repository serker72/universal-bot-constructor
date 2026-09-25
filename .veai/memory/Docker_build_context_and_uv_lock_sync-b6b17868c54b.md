---
name: Docker build context and uv.lock sync
description: "app/Dockerfile build context is repo root; uv sync --locked; uv.lock and package-lock must stay in sync"
type: project
lastUpdated: 2026-09-24T22:48
---

- Образы `app/Dockerfile` и `app/Dockerfile.test` собираются с контекстом КОРНЯ проекта (`docker build -f app/Dockerfile .`), т.к. `uv.lock` workspace лежит в корне; корневой `.dockerignore` — allowlist (pyproject, uv.lock, app/src, app/alembic, app/tests).
- Зависимости ставятся `uv sync --locked` (uv 0.7.19 закреплён). Сборка падает, если `uv.lock` рассинхронизирован с `app/pyproject.toml`.
- **Why:** прежний `uv pip install -e .` игнорировал lock и скрывал рассинхрон — в 2026-09 в uv.lock отсутствовал `nh3` (зависимость app), обнаружено только при переходе на lock. Аналогично `frontend/package-lock.json` был рассинхронизирован, что скрывал `npm ci || npm install`.
- **How to apply:** после изменения зависимостей в `app/pyproject.toml` выполнить `uv lock`; во frontend — `npm install` (обновить lock) перед сборкой.
- Node на хосте установлен через nvm (v24, npm 11): в неинтерактивном shell сначала `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"` — иначе `node`/`npx` не находятся в PATH.

