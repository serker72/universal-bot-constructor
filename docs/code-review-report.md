# 📋 Отчёт по анализу кода проекта universal-bot-constructor

Дата анализа: 2026-09-19

Обзор: backend (FastAPI, dishka, SQLAlchemy), bot (aiogram, aiogram-dialog), frontend (Nuxt.js), инфраструктура (docker compose, nginx, pgbouncer, redis, rabbitmq).

---

## 🔴 Критичные проблемы безопасности

### 1. `BACKEND_JWT_SECRET` по умолчанию — пустая строка
`app/src/app/config/settings.py:164` — `jwt_secret: str = ""`. Если переменная не задана в `.env`, токены подписываются пустым секретом → **любой может подделать JWT** и получить доступ admin. Нет fail-fast валидации при старте приложения.
**Рекомендация:** добавить в `Settings`/`create_app()` проверку «секрет обязателен и ≥ 32 байт», иначе — отказ запуска.

### 2. Пароль БД (md5-хеш) закоммичен в git
`srv/pgbouncer/userlist.txt` — **отслеживается git'ом** и содержит реальный md5-хеш пароля PostgreSQL (одинаковый для всех трёх пользователей). Md5-хеш без соли поддаётся брутфорсу (rainbow tables).
**Рекомендация:** удалить файл из git (`git rm --cached`), добавить в `.gitignore`, генерировать при деплое (скрипт `gen_userlist.sh` уже есть).

### 3. Rate-limit логина неработоспособен за прокси + глобальный DoS
`app/src/app/api/routers/auth.py:23` — `request.client.host`. За nginx **все клиенты имеют один IP** (адрес контейнера nginx), т.к. uvicorn не сконфигурирован с `--proxy-headers` / `ProxyHeadersMiddleware`, а `X-Forwarded-For` игнорируется. Итог:
- лимит 10 попыток/мин становится **общим для всех пользователей** → легитимные пользователи блокируются (DoS логина);
- реальный IP атакующего не виден.
**Рекомендация:** включить `uvicorn --proxy-headers --forwarded-allow-ips`, использовать `X-Forwarded-For`; ключ лимита делать составным: `login:{ip}:{username}`.

### 4. Неатомарный rate-limit (INCR + EXPIRE)
`app/src/app/services/security.py:37-39` — если процесс упадёт между `INCR` и `EXPIRE`, ключ останется **без TTL навсегда** → перманентная блокировка IP.
**Рекомендация:** Lua-скрипт или `SET key 1 EX ttl NX` + `INCR`.

### 5. `pgbouncer auth_type = md5`
`srv/pgbouncer/pgbouncer.ini` — устаревшая схема аутентификации. PostgreSQL и pgbouncer поддерживают `scram-sha-256`.
**Рекомендация:** перевести PostgreSQL и pgbouncer на `scram-sha-256`.

---

## 🟠 Средние проблемы безопасности

### 6. HTML-инъекция в сообщениях бота
`app/src/app/bot/handlers/menu.py:125` — `parse_mode="HTML"` + `obj.name` без экранирования. Если в названии объекта/категории будут теги (`<b>`, `<i>` или незакрытый `<`), Telegram вернёт ошибку парсинга или «сломает» разметку сообщения.
**Рекомендация:** `from aiogram import html; f"<b>{html.quote(obj.name)}</b>"`.

### 7. bcrypt молча обрезает пароли длиннее 72 байт
`app/src/app/services/password.py` + `UserIn.password max_length=128`. Разрешены 128 символов, но bcrypt использует только первые 72 байта — разные «длинные» пароли могут давать один хеш. Не критично, но вводит в заблуждение.
**Рекомендация:** ограничить `max_length=72` или явно проверять длину в байтах.

### 8. Слабая политика паролей
`min_length=8` без требований к сложности. Для админ-панели желательно минимум 10–12 + проверку на распространённые пароли.

### 9. `/api/docs` (Swagger) доступен без авторизации
`app/src/app/api/main.py:50`. Для dev — удобно, для prod — раскрывает всю поверхность API.
**Рекомендация:** отключать `docs_url` при `environment == "prod"`.

### 10. `drop_pending_updates=True` в webhook
`app/src/app/bot/main.py:41` — при каждом рестарте контейнера бота **все накопленные апдейты Telegram отбрасываются** (регистрации, нажатия кнопок пользователей теряются).
**Рекомендация:** убрать `drop_pending_updates` из `set_webhook` (оставить только в long-polling при dev).

### 11. Роль пользователя доверяет localStorage (frontend)
`frontend/composables/useAuth.ts` + `middleware/auth.global.ts` — роль берётся из localStorage. Подделка откроет админские страницы UI (API корректно вернёт 403, данных не утечёт, но UX-ошибка). Приемлемо, но лучше после login/refresh запрашивать `/auth/me` с сервера.

### 12. Политика cookies зависит от ручной настройки
`cookie_secure: bool = False` по умолчанию. Для prod легко забыть включить. Лучше выводить `secure` из `url_scheme == "https"` автоматически.

---

## 🔁 Дублирование кода

### 13. `set_managers` — почти идентичные ~25 строк в двух роутерах
`app/src/app/api/routers/categories.py:115-141` и `objects.py:136-160`: проверка существования пользователей, diff множеств, add/remove в цикле. Отличаются только именами сущностей.
**Рекомендация:** вынести общий helper `sync_managers(repo, entity_id, user_ids, users)`.

### 14. Дублирование методов менеджеров в репозиториях
`CategoryRepository.add_manager/remove_manager/list_manager_ids` ↔ `ObjectRepository.add_manager/remove_manager/list_manager_ids` — идентичная логика на разных link-моделях.
**Рекомендация:** generic-базовый класс `ManagerLinkRepository[TLink]`.

### 15. Дублируется логика «прямые ∪ через категорию»
`ObjectRepository.list_access_manager_ids` (object.py:68-84) и `RequestRepository.list_manager_object_ids` (request.py:71-84) — одна и та же операция объединения связей, в двух местах.
**Рекомендация:** единый метод в одном репозитории.

### 16. Повторяющаяся проверка посетителя в хендлерах бота
Паттерн `get_visitor → None → alert «Сначала завершите регистрацию» → is_blocked → alert` повторяется **5+ раз**: `menu.py:24` (ensure_visitor), `requests.py:41,74,101,128`, `request_dialog.py:318-322`. При этом `ensure_visitor` уже есть, но используется только в menu.py.
**Рекомендация:** использовать `ensure_visitor` везде либо aiogram-middleware.

### 17. Три копии словаря статусов заявки
`bot/keyboards.py:12` (STATUS_EMOJI), `bot/handlers/requests.py:21` (STATUS_TEXT), `bot/notifications.py:32` (STATUS_TEXT). При добавлении статуса нужно править три места.
**Рекомендация:** единый модуль `bot/statuses.py`.

### 18. `PHONE_RE` определён дважды
`app/src/app/bot/services.py:16` (не используется — мёртвый код) и `app/src/app/bot/validators.py:5`.
**Рекомендация:** удалить из services.py.

### 19. Шаблон CRUD-роутеров
`get → None → 404 → изменить поля → validate` повторяется в categories/objects/users (~10 раз). Мелочь, но можно dependency `get_or_404(repo, id, msg)`.

### 20. Frontend: копипаста страниц и `limit: 1000`
Во всех 8 страницах дублируется `load/changeOffset/modal/save`-скелет; в 6 местах — «подгрузка всего списка» через `limit: 1000` (`/users`, `/categories`, `/objects`). Нет выделенного composable (например, `useCrudPage`), а «выкачать всё» не масштабируется.

---

## 🐌 Неэффективные подходы

### 21. Пагинация сессий в Python вместо SQL
`app/src/app/api/routers/sessions.py:27-29` — при фильтре по `user_id` загружаются **все** сессии пользователя (`list_by_user` без limit), а срез делается в Python `items[offset:offset+limit]`. У активного пользователя с историей входов — лишние сотни строк из БД.
**Рекомендация:** добавить limit/offset в `SessionRepository.list_by_user` (как сделано в `find()`).

### 22. N+1 запросов при назначении менеджеров
`categories.py:129-134`, `objects.py:149-154` — `users.get(user_id)` в цикле. Для 50 менеджеров — 50 запросов.
**Рекомендация:** один запрос `users.find(User.id.in_(data.user_ids))` + сравнение множеств.

### 23. Последовательные записи в Redis при массовом отзыве
`app/src/app/services/auth.py:216-220` — `blacklist.add` в цикле, по одному round-trip на сессию.
**Рекомендация:** `redis.pipeline()`.

### 24. Последовательная рассылка уведомлений
`app/src/app/bot/notifications.py:135-141` — `send_message` по одному, без параллелизма. При большом числе админов обработка сообщения из очереди затягивается (aiogram сам throttle'ит по лимитам Telegram, но `asyncio.gather` с семафором ускорит в разы).

### 25. PDF читается целиком в память до проверки размера
`app/src/app/api/routers/pdf.py:28-32` — `await file.read()` сначала, валидация размера потом. Nginx ограничивает 25МБ, но при прямом доступе к `127.0.0.1:8000` (порт опубликован на localhost) лимита нет.
**Рекомендация:** проверять `file.size`/`Content-Length` до чтения, читать чанками.

### 26. `min_date`/`max_date` календаря фиксируются при импорте модуля
`app/src/app/bot/dialogs/request_dialog.py:339-343` — `date.today()` вычисляется один раз при старте процесса. Бот работает неделями: через месяц `min_date` устареет (можно выбрать дату в прошлом), при перезапуске «прыгнет» вперёд.
**Рекомендация:** вычислять даты в геттере окна на каждый рендер.

### 27. Бесполезный `or_()` с одним аргументом
`app/src/app/repository/visitor.py:30` — `or_(Visitor.full_name.ilike(pattern))` эквивалентен самому условию. Видимо, остаток от удалённого поиска по телефону.

### 28. Два запроса (find + count) на каждую страницу списка
`bot/services.py` (list_categories/list_objects/list_visitor_requests) и все list-роутеры. Для текущих объёмов приемлемо; при росте — `count(*) over ()` в одном запросе.

---

## 🟡 Мелочи / потенциальные проблемы

| # | Место | Проблема |
|---|-------|----------|
| 29 | `api/routers/users.py:42-45` | TOCTOU: проверка уникальности username в коде; при гонке двух запросов — `IntegrityError` без обработки (вернётся 500 вместо 400). Unique-constraint в БД есть — обернуть в try/except как в `create_object` |
| 30 | `api/routers/objects.py:109-119` | Удаление объекта не удаляет PDF-файл с диска (`pdf.delete` вызывается только при перезагрузке) → накопление осиротевших файлов |
| 31 | `api/routers/objects.py:90-106` | PATCH требует **все** поля (ObjectIn без опциональности) — это фактически PUT-семантика под PATCH |
| 32 | `services/auth.py:211-221` | `revoke_all_for_user` — если Redis недоступен, сессии отзовутся в БД, но blacklist не заполнится: access-токены продолжат работать до 30 мин. Допустимый компромисс, но стоит логировать ошибку |
| 33 | `bot/notifications.py:68-93` | Индексация `queues[0..3]` — хрупко при добавлении очереди; словарь name→queue надёжнее |
| 34 | `main.py` (корень) | Мёртвый файл-заготовка «Hello world» — удалить |
| 35 | `.env.example:48` | `SQLALCHEMY_DEBUG=True` в примере — SQL со всеми параметрами в логах; для примера лучше `False` |
| 36 | `srv/nginx/conf/default.conf` | Нет HTTPS (443 закомментирован), нет security-заголовков (`X-Content-Type-Options`, `X-Frame-Options`), нет rate-limit на уровне nginx |
| 37 | `docker-compose.backend.yml:25` | Порт backend опубликован на `127.0.0.1` — хорошо, но помечает, что обход nginx (п.25) возможен локально |
| 38 | `frontend/pages/*.vue` | `catch (err)` без использования переменной — ошибка от API глотается, пользователь видит только общий текст |

---

## Итоговая сводка

| Категория | Критично | Средне | Низко | Всего |
|---|---|---|---|---|
| Безопасность | 5 | 7 | — | 12 |
| Дублирование | — | 4 | 4 | 8 |
| Неэффективность | — | 4 | 4 | 8 |
| Прочее | — | — | 10 | 10 |

**Топ-5 для исправления в первую очередь:**
1. Валидация `JWT_SECRET` при старте (п.1)
2. Убрать `userlist.txt` из git + scram-sha-256 (п.2, п.5)
3. Proxy-headers для реального IP + ключ rate-limit (п.3)
4. Убрать `drop_pending_updates` из webhook (п.10)
5. Атомарный rate-limit (п.4)

---

## 📝 Статус исправлений (в процессе работы)

- [x] п.1 — Валидация `BACKEND_JWT_SECRET` (fail-fast, ≥32 байт в prod) + `cookie_secure` из `url_scheme` — `app/src/app/config/settings.py`
- [x] п.2 — `srv/pgbouncer/userlist.txt` убран из git (`.gitignore`, `git rm --cached`), перегенерирован через `gen_userlist.sh`
- [x] п.5 — pgbouncer `auth_type = scram-sha-256` — `srv/pgbouncer/pgbouncer.ini`
- [x] п.3 — uvicorn `--proxy-headers --forwarded-allow-ips='*'` — `docker-compose.backend.yml`; `_client_ip()` из `X-Forwarded-For` + составной ключ `login:{ip}:{username}` — `app/src/app/api/routers/auth.py`
- [x] п.4 — Атомарный rate-limit через Lua (INCR+EXPIRE) + `add_many` через pipeline — `app/src/app/services/security.py`, тесты обновлены (`app/tests/unit/test_security.py`)
- [x] п.6 — HTML-экранирование `obj.name`/`short_description` (`aiogram.html.quote`) — `app/src/app/bot/handlers/menu.py`
- [x] п.7 — bcrypt: ограничение 72 байта + `validate_password_policy` — `app/src/app/services/password.py`, `app/src/app/api/schemas/user.py` (max_length 128→72)
- [x] п.8 — Политика паролей: проверка 8–72 байта в `hash_password` — `app/src/app/services/password.py`
- [x] п.9 — Swagger/OpenAPI отключаются в prod — `app/src/app/api/main.py`
- [x] п.10 — Убран `drop_pending_updates` из `set_webhook` — `app/src/app/bot/main.py`
- [x] п.11 — Добавлен эндпоинт `GET /auth/me` — `app/src/app/api/routers/auth.py` (frontend-интеграция — в работе)
- [x] п.12 — `cookie_secure` выводится из `PROJECT_URL_SCHEME` автоматически — `app/src/app/config/settings.py`
- [x] п.13 — Общий helper `sync_managers` (проверка пользователей batch-запросом + diff + add/remove) — новый `app/src/app/api/managers_sync.py`; роутеры `categories.py`/`objects.py` используют его (дублирующие ~25 строк удалены из обоих)
- [x] п.14 — `ManagerLinkMixin` (add/remove/list менеджеров) — новый `app/src/app/repository/manager_link.py`; `ObjectRepository` и `CategoryRepository` наследуют mixin вместо дублирующихся методов
- [x] п.15 — Логика «прямые ∪ через категорию» в единственном месте: `list_access_manager_ids` + `list_manager_object_ids` — `app/src/app/repository/object.py`; из `RequestRepository` удалён дубль, роутер `requests.py` использует `ObjectRepository`
- [x] п.16 — `ensure_visitor` используется во всех хендлерах заявок (4 места) вместо копипасты проверки — `app/src/app/bot/handlers/requests.py`
- [x] п.17 — Единый модуль статусов `app/src/app/bot/statuses.py` (STATUS_EMOJI / STATUS_TEXT / STATUS_NOTIFY_TEXT); keyboards.py, handlers/requests.py, notifications.py импортируют из него
- [x] п.18 — Мёртвый `PHONE_RE` удалён из `app/src/app/bot/services.py` (остался единственный в `validators.py`)
- [x] п.19 — Helper `get_or_404` — `app/src/app/api/deps.py`; применён в роутерах categories/objects/users/sessions/visitors/devices/pdf/requests (14 мест)
- [x] п.21 — Пагинация сессий в SQL: `SessionRepository.list_by_user` теперь возвращает `(items, total)` с limit/offset; роутер `sessions.py` и `AuthService.revoke_all_for_user` обновлены
- [x] п.22 — N+1 при назначении менеджеров устранён: `UserRepository.list_by_ids` (batch `id IN (...)`) — вместе с п.13
- [x] п.23 — `TokenBlacklist.add_many` через redis-pipeline; `revoke_all_for_user` пишет одним round-trip — `app/src/app/services/security.py`, `auth.py`
- [x] п.24 — Параллельная рассылка `_send_all` (`asyncio.gather` + Semaphore(10)) — `app/src/app/bot/notifications.py`
- [x] п.25 — Размер PDF проверяется до чтения (`file.size` + повторная проверка после read) — `app/src/app/api/routers/pdf.py`
- [x] п.26 — `CalendarConfig` вычисляется в геттере окна на каждый рендер (`_calendar_getter`), не при импорте — `app/src/app/bot/dialogs/request_dialog.py`
- [x] п.27 — Убран бесполезный `or_()` — `app/src/app/repository/visitor.py`
- [x] п.28 — Осознанно оставлено: find + count (2 запроса на страницу) — приемлемо при текущих объёмах; при росте → `count(*) over ()`
- [x] п.29 — `IntegrityError` обрабатывается в `create_user` (гонка username/telegram_id → 400, rollback) — `app/src/app/api/routers/users.py`
- [x] п.30 — PDF удаляется с диском: при удалении объекта и категории (CASCADE) — `app/src/app/api/routers/objects.py`, `categories.py`
- [x] п.31 — PATCH-семантика: `ObjectUpdateIn`/`CategoryUpdateIn` (все поля опциональны, None = не менять) — `app/src/app/api/schemas/object.py`, `category.py`; роутеры обновлены
- [x] п.32 — Ошибка Redis при массовом отзыве логируется (`blacklist_unavailable_on_revoke_all`), сессии отзываются в БД — `app/src/app/services/auth.py`
- [x] п.33 — Очереди в словаре по именам (`queues["registration"]` и т.д.) вместо индексов — `app/src/app/bot/notifications.py`
- [x] п.34 — Мёртвый `main.py` в корне удалён
- [x] п.35 — `SQLALCHEMY_DEBUG=False` в `.env.example` (+ предупреждение в комментарии)
- [x] п.20 — Composable `useManagers` (однократная загрузка списка менеджеров, переиспользуется между страницами) — `frontend/composables/useManagers.ts`; pages/categories.vue, objects.vue используют его
- [x] п.11 (frontend-часть) — `fetchMe()` (GET /auth/me) в `useAuth`; middleware сверяет роль с сервером при каждой навигации — `frontend/composables/useAuth.ts`, `middleware/auth.global.ts`
- [x] п.38 — Все bare-catch заменены на `catch (err)` + `console.warn` с контекстом — все 9 страниц frontend (сборка `nuxt build` прошла успешно)
- [x] п.36 — Security-заголовки nginx: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection` (always) — сейчас в `srv/nginx/templates/{loc,prod}/*.template`; HTTPS (443) — реализовано 24.09.2026 для prod (`ssl.conf.template`, HSTS, certbot — `docker-compose.nginx.prod.yml`, `init-letsencrypt.sh`)
- [x] п.37 — Осознанно оставлено: порт backend на 127.0.0.1 (удобно для локальной отладки); при prod-деплое можно закрыть

---

## ✅ Итог верификации (docker)

- **Unit-тесты: 107 passed** (в т.ч. обновлённые `test_security.py` под Lua rate-limit, `test_password.py` под политику 8–72 байта)
- **Интеграционные тесты: 116 passed, 0 failed** (auth, users, sessions, devices, categories, objects, pdf, requests, visitors, settings, repositories, auth_service; обновлены под новую сигнатуру `SessionRepository.list_by_user → (items, total)`)
- Приложения пересобраны и запущены: backend (health `{"status":"ok"}`), bot (`bot_started_polling`), nginx (security-заголовки на ответах), pgbouncer/postgres/redis/rabbitmq — healthy

## 🔧 Технические решения в процессе исправлений

1. **`ManagerLinkMixin` + `link_entity()`** — дескриптор колонки связи: `InstrumentedAttribute` SQLAlchemy при доступе через инстанс репозитория ломается (это ORM-дескриптор), поэтому колонка оборачивается в `_LinkAttr` (всегда возвращает колонку). Имя колонки для конструктора связи берётся из `.key` (`object_id` / `category_id`).
2. **Fail-fast JWT** — проверка в `Settings._validate_security` (model_validator): пустой секрет → отказ запуска; в prod — ≥ 32 байт.
3. **Rate-limit** — Lua `INCR`+`EXPIRE` (атомарно), ключ `login:{ip}:{username}`, IP из `X-Forwarded-For` (uvicorn `--proxy-headers`).
4. **`cookie_secure`** — `None`-default → выводится из `PROJECT_URL_SCHEME` (https → True).
5. **scram-sha-256** — pgbouncer переключён, userlist с plaintext-паролями (требование pgbouncer для SCRAM), файл выведен из git.
