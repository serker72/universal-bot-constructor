---
name: API transaction commit before response
description: TransactionalRoute commits DB session before FastAPI response; dishka REQUEST finalizer runs after response is sent
type: project
lastUpdated: 2026-09-24T22:34
---

- dishka закрывает REQUEST-scope (финализатор сессии с commit) ПОСЛЕ отправки ответа FastAPI: ошибка commit давала клиенту 200 при фактическом откате.
- Решение: все роутеры используют `app.api.routing.TransactionalRoute` (DishkaRoute + commit/rollback до ответа). Ошибки уникальности/FK ловить через `flush_or_400` (app/api/deps.py) до формирования ответа; после flush с server onupdate (`updated_at`) делать `session.refresh(obj)` перед сериализацией (иначе MissingGreenlet).
- Бот: `CommitBeforeTelegramMiddleware` (request-middleware сессии Bot) коммитит транзакцию обновления перед каждым вызовом Telegram API (pgbouncer transaction mode не держит соединение на время сетевого I/O); контейнер обновления передаётся через contextvar (`UpdateContainerMiddleware`).
- **How to apply:** новые роутеры — `route_class=TransactionalRoute`; файловые операции (удаление PDF) — только после явного commit.

