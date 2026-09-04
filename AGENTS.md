# Описание проекта
Приложение "Универсальный конструктор меню бота Telegram".
Двухуровневая структура данных - категории, объекты.
Объект: id категории, наименование, краткое описание, файл pdf с полным описанием.

Список пользователей управляется администратором во frontend.
Список ролей:
- admin
- manager

Посетители регистрируются в боте: запрос ФИО, согласия на обработку персональных данных.

# Технологии
Состав:
- services - nginx, postgresql, redis, rabbitmq, pgbouncer
- backend - python, uv, fastapi, faststream, dishka, sqlalchemy, alembic, repository, services layer
- frontend - nuxt.js, tailwindcss
- bot - python, aiohttp, aiogram
- containers - docker, docker compose

# Запуск проекта
Запуск приложения выполняется с помощью `docker compose`.
Все переменные в файле `.env`.
Сервисы запускаются с помощью файла `docker-compose.srv.yml`. 
Для запуска приложений `backend, bot` используется виртуальная среда `.venv`.

# Запуск миграций Alembic (локально)
- alembic установлен в корневой виртуальной среде `.venv` (не в `app/.venv`), рабочая директория — `app/`
- пакет `app` не установлен в venv, поэтому требуется `PYTHONPATH=app/src`
- в `.env` хост `pgbouncer` резолвится только внутри docker-сети, при локальном запуске переопределять: `POSTGRES_HOST=127.0.0.1` (pgbouncer публикует порт на localhost)

Команда применения миграций (из корня проекта):
```bash
PYTHONPATH=app/src POSTGRES_HOST=127.0.0.1 .venv/bin/alembic -c app/alembic.ini upgrade head
```

Команда создания новой миграции (из каталога `app/`):
```bash
PYTHONPATH=../app/src POSTGRES_HOST=127.0.0.1 ../.venv/bin/alembic revision -m "{message}"
```

Альтернатива через docker (имена из `.env` резолвятся внутри сети):
```bash
docker compose -f docker-compose.dbupdate.yml run --rm db-update
```
