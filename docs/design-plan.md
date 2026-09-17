# План проектирования системы «Универсальный конструктор меню бота Telegram»

> Этот файл содержит полный план проектирования и все договорённости, собранные в ходе обсуждения.
> Используется для восстановления контекста в новой сессии.

---

## Описание проекта

Приложение «Универсальный конструктор меню бота Telegram».
Двухуровневая структура данных — категории, объекты.
Объект: id категории, наименование, краткое описание (HTML/Markdown), файл PDF с полным описанием.

Один бот на весь проект. Структура меню управляется админом/менеджером через frontend.

## Роли

- **admin** — управляет пользователями, настройками, контентом (категории/объекты), видит все заявки (но не обрабатывает), банит/разбанивает посетителей, управляет сессиями/устройствами.
- **manager** — управляет только своими объектами (через таблицу связи объект↔менеджер), видит и обрабатывает заявки по своим объектам.

Регистрация админ/менеджер-пользователей — только вручную через frontend (создаёт админ).

## Технологии

- **services**: nginx, postgresql, redis, rabbitmq, pgbouncer
- **backend**: python, uv, fastapi, faststream, dishka, sqlalchemy (async), alembic (async), asyncpg, repository/services layer
- **frontend**: nuxt.js, tailwindcss
- **bot**: python, aiohttp, aiogram, aiogram-dialog
- **containers**: docker, docker compose (единый файл)

## Запуск

- Docker compose, все переменные в `.env`.
- dev — long-polling, prod — webhook через nginx.
- HTTPS/certbot — позже.

---

## План проектирования (8 шагов)

### Шаг 1. Docker compose и инфраструктура

Compose-файлы разделены по назначению:

- **`docker-compose.srv.yml`** — инфраструктурные сервисы без приложений:
  - **nginx** — reverse proxy (frontend, backend API, webhook бота в prod)
  - **postgresql** — СУБД
  - **pgbouncer** — пул соединений к одной БД
  - **redis** — кэш/сессии/FSM/blacklist/rate-limit
  - **rabbitmq** — брокер для faststream
- **`docker-compose.backend.yml`** — приложение backend:
  - **backend** — FastAPI (API + миграции alembic)
  - **bot** — aiogram (dev: long-polling; prod: webhook через nginx)
- **`docker-compose.frontend.yml`** — приложение frontend:
  - **frontend** — Nuxt.js
- **`docker-compose.yml`** — единый файл, включает все сервисы и приложения
  (через `include:` для трёх файлов выше)

Все переменные окружения — в `.env`. Значения читаются через **pydantic-settings**:
классы конфигурации разделены по префиксам имён переменных:

- `POSTGRES_*` — параметры PostgreSQL
- `PGBOUNCER_*` — параметры PgBouncer
- `REDIS_*` — параметры Redis
- `RABBITMQ_*` — параметры RabbitMQ
- `BACKEND_*` — параметры backend (FastAPI)
- `BOT_*` — параметры бота (aiogram), включая `BOT_PROXY_URL` для AioHTTP-сессии
- `FRONTEND_*` — параметры frontend (Nuxt.js)
- `NGINX_*` — параметры nginx

### Шаг 2. Схема БД (миграции alembic)

Таблицы:

- **categories** — id, name, sort_order, is_active, created_at, updated_at
- **objects** — id, category_id (FK), name, short_description (HTML/Markdown), pdf_path, sort_order, is_active, created_at, updated_at
- **object_managers** — object_id (FK), user_id (FK), связь многие-ко-многим
- **users** — id, username, password_hash, role (admin/manager), telegram_id (nullable), is_active, created_at, updated_at
- **visitors** — id, telegram_id (unique), full_name, phone (nullable, сохраняется при регистрации и обновляется в диалоге заявки), consent_given (bool), consent_at (timestamp), is_blocked (bool), blocked_at (timestamp), created_at, updated_at
- **requests** (заявки) — id, visitor_id (FK), object_id (FK), phone (string, контролируется только формат), comment (nullable), start_date (date, nullable), start_time (time, nullable), end_date (date, nullable), end_time (time, nullable), status (enum: new/approved/rejected/completed/cancelled_by_customer), created_at, updated_at, confirmed_at (nullable, для расчёта интервала отмены)
- **devices** — id, user_id (FK), device_id (thumbmarkjs), user_agent, created_at, last_seen_at
- **sessions** — id, device_id (FK), user_id (FK), refresh_token_jti, is_active, created_at, revoked_at
- **settings** — key, value (размер страницы бота по умолчанию=10, интервал отмены подтверждённой заявки в часах=24, текст согласия, текст приветствия бота, флаги заявки: is_use_time_in_request=false, is_use_end_date_in_request=false)

### Шаг 3. Внутренняя архитектура backend

- Слои: **repository** (SQLAlchemy async) → **services** (бизнес-логика) → **routers** (FastAPI)
- DI: **dishka**
- Асинхронный стек: **asyncpg** (драйвер), **SQLAlchemy async**, **alembic async** для миграций
- **faststream** + RabbitMQ: события для уведомлений (новая регистрация → админ; новая заявка/отмена → менеджер)
- **Redis**: кэш, сессии frontend, FSM aiogram, rate-limit, blacklist JWT (оба токена с TTL)
- Логирование: **logging + structlog**

### Шаг 4. REST API (FastAPI)

Эндпоинты:

- **auth**: login, refresh, logout (access+refresh в httpOnly cookies; оба токена заносятся в blacklist в Redis с TTL при logout/отзыве)
- **categories**: CRUD + сортировка + флаг активности
- **objects**: CRUD + сортировка + флаг активности + назначение менеджеров
- **pdf**: загрузка (multipart/form-data, только PDF, ≤20МБ), получение (endpoint с авторизацией, открытие в новой вкладке)
- **users**: список, создание, редактирование, удаление (только admin)
- **visitors**: список, поиск/фильтр, бан/разбан (только admin)
- **requests**: список с фильтрами (статус, дата, объект); менеджер видит только свои; админ видит все; подтверждение/отклонение (менеджер)
- **devices**: список с фильтрацией по пользователю
- **sessions**: список, отзыв одной/всех сессий (с отзывом токенов)
- **settings**: чтение/обновление (только admin)

### Шаг 5. Бот (aiogram)

- Команда `/start`:
  - Если незарегистрирован → flow регистрации (ФИО → телефон → согласие). Регистрация повторяется до завершения, пока не завершена — всегда попадает в меню регистрации.
  - Если заблокирован → сообщение «Вы заблокированы», меню не открывается.
  - Если зарегистрирован → главное меню.
- **Главное меню**: список категорий (пагинация по N из настроек, по умолчанию 10, кнопки ◀️/▶️ с номером страницы) → список объектов (пагинация) → страница объекта (наименование, краткое описание, кнопка «Получить PDF» → Telegram-документ, кнопка «Создать заявку»).
- **Создание заявки**: диалог aiogram-dialog (телефон → даты/время по флагам → комментарий) → заявка в статусе «новая» → уведомление менеджеру.
- **Пункт «Мои заявки»**: список заявок посетителя, просмотр статуса, кнопка «Отменить»:
  - Статус «новая» — отмена в любой момент.
  - Статус «подтверждена» — отмена в пределах интервала из настроек (по умолчанию 24ч от подтверждения).
  - Иные статусы — отмена недоступна.
- **Уведомления** (через bot по telegram_id из карточки пользователя):
  - Админу — о новой регистрации.
  - Менеджеру — о новой заявке и об отмене заявки по его объектам.
  - Если telegram_id не указан — уведомление пропускается (не ошибка).
- Согласие: фиксированный текст (из настроек), хранится флаг + время в профиле посетителя.

### Шаг 6. Frontend (Nuxt.js + Tailwind) и запуск всех приложений через docker-compose

Страницы/маршруты:

- **/login** — вход
- **/dashboard** — дашборд
- **/categories** — категории (CRUD, сортировка, активность)
- **/objects** — объекты (CRUD, сортировка, активность, назначение менеджеров, загрузка PDF)
- **/requests** — заявки (фильтры по статусу/дате/объекту; менеджер — свои, админ — все; подтверждение/отклонение менеджером)
- **/requests** — заявки (фильтры по статусу/дате/объекту; менеджер — свои, админ — все; подтверждение/отклонение менеджером)
- **/users** — пользователи (только admin)
- **/users** — пользователи (только admin)
- **/visitors** — посетители (бан/разбан, поиск/фильтр; только admin)
- **/devices** — устройства (фильтр по пользователю)
- **/sessions** — сессии (фильтр по пользователю, отзыв одной/всех)
- **/settings** — настройки (только admin)

Особенности:

- **device_id** определяется через **thumbmarkjs** на стороне frontend.
- **JWT** (access+refresh) — в httpOnly cookies, выдаются на каждое устройство свои.
- **PDF** открывается в новой вкладке (endpoint backend с авторизацией).
- Язык интерфейса — только русский.
- Часовой пояс: UTC в БД, Europe/Moscow — в интерфейсе.

Запуск всех приложений — через **docker-compose**:

- `docker-compose.yml` (единый файл через `include:`) поднимает весь стек:
  сервисы (nginx, postgresql, pgbouncer, redis, rabbitmq) + backend + bot + frontend;
- проверка совместной работы: frontend ↔ nginx ↔ backend ↔ pgbouncer/postgresql,
  bot ↔ redis/rabbitmq, сети `ubc-backend` / `ubc-frontend`, переменные из `.env`;
- локальная разработка без docker — как раньше: `.venv` для backend/bot,
  `npm run dev` для frontend.

### Шаг 7. Тесты (unit и интеграционные)

Unit-тесты (быстрые, без внешних зависимостей):

- **validators** — нормализация/контроль формата телефона (bot);
- **services** — `TokenService` (создание/валидация JWT), `PdfService`
  (валидация PDF, сохранение/чтение/удаление, tmp-каталог);
- **keyboards/callbacks** — pack/unpack callback-данных, генерация клавиатур;
- **bot service** — `BotService.can_cancel` (new/approved/интервал отмены) на
  моках репозиториев.

Интеграционные тесты (реальная БД/Redis/RabbitMQ через docker-compose):

- **API**: auth (login/refresh/logout, cookies, blacklist, rate-limit),
  CRUD categories/objects/users, права admin/manager (403), заявки
  (видимость, переходы статусов), visitors (поиск/бан), sessions/devices,
  settings (валидация ключей);
- **bot**: регистрация посетителя, меню с пагинацией, создание заявки,
  отмена (правила интервалов), уведомления через RabbitMQ-консьюмеры;
- тестовая БД `universal_bot_constructor_test` (переменные `POSTGRES_TEST_*`),
  миграции применяются перед прогоном; фикстуры pytest-asyncio.

### Шаг 8. Итоговый документ проектирования

Зафиксировать в файле проекта: архитектура, ER-модель, API-контракты, потоки данных.

---

## Диалог создания заявки на aiogram-dialog

> Расширение сценария создания заявки (Шаг 5): многооконный диалог с выбором
> дат и времени, управляемый флагами из таблицы `settings`.

### Новые флаги конфигурации (таблица settings)

- `is_use_time_in_request` (bool, default `false`) — использовать время в запросе;
- `is_use_end_date_in_request` (bool, default `false`) — использовать дату окончания в запросе.
- Управление — через frontend `/settings` (admin), чтение в боте через `AppSettingsService`.

### Изменения схемы БД (миграции alembic)

- `visitors`: добавить колонку `phone` (String(32), nullable) — сохраняется при регистрации,
  обновляется при вводе нового номера в диалоге заявки; используется геттером профиля.
- `requests`: добавить колонки (все nullable, т.к. зависят от флагов):
  - `start_date` (Date), `start_time` (Time), `end_date` (Date), `end_time` (Time).
- Миграции создаются по инструкции из системного промпта (alembic в корневой `.venv`, `PYTHONPATH=app/src`, `POSTGRES_HOST=127.0.0.1`).

### Зависимости

- Добавить пакет `aiogram-dialog` в зависимости `app/pyproject.toml`.

### Виджет RuCalendar

- Штатный `Calendar` из `aiogram-dialog` не переводит названия месяцев и дней недели
  (официальная документация: «it doesn't translate any dates. If you want localized month
  or week day names you should provide your own Text widget»).
- Поэтому реализуется виджет **`RuCalendar`** — подкласс `Calendar` с переопределением
  `_init_views()`: русские названия месяцев (`header_text=Format(...)` + словарь месяцев),
  дни недели Пн–Вс, кнопки навигации «◀️/▶️», кнопка «Сегодня».
- `CalendarConfig(firstweekday=0)` — неделя с понедельника.

### Состояния RequestStates

Заменяются на:

- `input_phone`
- `start_date`
- `start_hour`
- `start_min`
- `end_date`
- `end_hour`
- `end_min`
- `input_comment`

Порядок прохождения зависит от флагов `is_use_time_in_request` /
`is_use_end_date_in_request` (см. «Динамический роутинг»).

### Геттер профиля пользователя

- Асинхронный getter окна `input_phone`: запрос к БД через `BotService` —
  извлечь сохранённый телефон (`visitors.phone`) по `telegram_id`;
  в `dialog_data` кладётся `profile_phone` (или `None`).
- Текст окна: «Ваш номер: +7...» (если есть) или приглашение ввести номер.

### Генераторы списков времени

- `generate_hours()` → `[(label "00"…"23", value 0…23)]` — часы 00–23;
- `generate_minutes(step=5)` → `[(label "00","05",…,55, value 0…55)]` — минуты с шагом 5;
- используются как `items` для виджетов `Select` в окнах выбора времени.

### Вёрстка окон диалога (6 окон)

1. **Окно 1 (Телефон, `input_phone`)**: текст с текущим номером из профиля (если есть),
   кнопка «Использовать номер из профиля» (показывается при наличии номера, `when=`),
   `MessageInput` для перехвата нового номера (текст/контакт) с нормализацией
   (`normalize_phone`), сохранение в `dialog_data["phone"]`.
2. **Окна 2 и 4 (Даты, `start_date` / `end_date`)**: интеграция виджета `RuCalendar`
   для начальной и конечной даты; выбор записывается в `dialog_data["start_date"]` /
   `dialog_data["end_date"]`.
3. **Окна 3 и 5 (Время, `start_hour`/`start_min`, `end_hour`/`end_min`)**: `Group`/`Row`
   с виджетами `Select` (часы 00–23, минуты с шагом 5).
4. **Окно 6 (Комментарий, `input_comment`)**: `MessageInput` — текст комментария или «-»
   (пустой/«-» → `comment=None`).

### Проброс флагов через start_data

- При старте диалога флаги читаются из настроек (`AppSettingsService`) и передаются:
  `dialog_manager.start(RequestStates.input_phone, data={"is_use_time_in_request": ..., "is_use_end_date_in_request": ...})`.
- В обработчиках флаги извлекаются как `manager.start_data.get("is_use_...")`.

### Динамический роутинг диалога

**Прямая навигация (Forward Routing)** — асинхронные обработчики `on_click` для каждого шага:
- после телефона → `start_date`;
- выбор начальной даты (обработчик `on_click` `RuCalendar`) → если `is_use_time_in_request` →
  `switch_to(start_hour)`, иначе если `is_use_end_date_in_request` → `switch_to(end_date)`,
  иначе → `input_comment`;
- минуты начального времени (обработчик `on_click` виджета `Select` минут) — проверка
  `manager.start_data.get("is_use_end_date_in_request")`:
  `switch_to(end_date)` либо `input_comment`;
- конечная дата → `end_hour` (время включено) либо `input_comment`;
- конечные минуты → `input_comment`.

**Обратная навигация (Backward Routing)** — на этапах с вариативным предыдущим шагом
статические виджеты `SwitchTo` (кнопки «Назад») заменяются на динамические `Button`
с кастомными коллбеками:
- от «Даты окончания» — либо к «Времени начала» (`start_min`), либо к «Дате начала» (`start_date`);
- от «Минут начального времени» — либо к «Часам начального времени» (`start_hour`),
  либо к «Дате начала» (`start_date`).

**Сборка итогового объекта (финализация)** — функция агрегации из `dialog_data`:
телефон, даты, время; валидация бизнес-правил:
- если заданы обе даты — `end_date >= start_date` (сравнение дат);
- если заданы дата+время с обеих сторон — сравнение полных `datetime`
  (`end_dt >= start_dt`); при нарушении — сообщение об ошибке и возврат на шаг.
- далее — создание заявки через `BotService.create_request(...)`.

### Интеграция и замена старого сценария

- Удалить (или закомментировать) старые хэндлеры сбора данных заявки
  (`app/src/app/bot/handlers/requests.py`: `start_request`, `process_request_phone`,
  `process_request_comment` — FSM-версия на `RequestStates.phone/comment`).
- Зарегистрировать новый `Dialog` в главном роутере бота (`include_router` диалога).
- Убедиться, что при старте приложения вызывается `setup_dialogs(dp)` (`app/src/app/bot/main.py`).
- Обновить хэндлер кнопки «Создать заявку» (`CreateRequestCB`): вызов
  `dialog_manager.start(RequestStates.input_phone, data={...flags...})`.
- Связь с бизнес-логикой: передавать в `create_request` новые поля
  (`start_date`, `start_time`, `end_date`, `end_time`).
- После `manager.done()` — отправка пользователю уведомления об успешном создании заявки.

### Тесты (unit + интеграционные)

Unit-тесты (`app/tests/unit/`):

- `test_app_settings.py` — флаги `is_use_time_in_request` / `is_use_end_date_in_request`:
  значения по умолчанию (`false`), парсинг `true/1/yes/on/да`, нераспознанное значение → default;
- `test_time_items.py` — генераторы: часы 00–23 (24 элемента, метки «00»…«23»),
  минуты с шагом 5 (12 элементов, метки «00»…«55»);
- `test_ru_calendar.py` — тексты виджета: русские месяцы (`RuMonthText`),
  дни недели Пн–Вс (`RuWeekdayText`), заголовок «🗓 Сентябрь 2026»
  (`RuDaysHeaderText`), сборка `RuCalendar` с `CalendarConfig(firstweekday=0)`;
- `test_request_dialog.py` — логика диалога без запуска Telegram:
  `validate_request_data` (end_date < start_date → ошибка; равные даты и
  end_time < start_time → ошибка; корректные данные → None),
  `collect_request_data` (по флагам: время только при is_use_time, конец только
  при is_use_end_date, «-» → comment=None).

Интеграционные тесты (`app/tests/integration/`):

- `test_api_settings.py` — новые ключи в PUT/GET настроек;
- `test_api_requests.py` — `RequestOut` содержит `start_date/start_time/
  end_date/end_time` (nullable, отдаются в списке/карточке);
- `conftest.py` — фикстуры: `visitor` с `phone`, `request_obj` с датами/временем.

---

## Как использовать этот файл в новой сессии

1. Откройте новый диалог.
2. Скажите: *«Продолжи проектирование/реализацию системы по плану из файла `docs/design-plan.md`»*.
3. AI прочитает файл и восстановит полный контекст.

---

## Прогресс реализации

- **Шаг 1** — выполнен: `docker-compose.srv.yml` (nginx, postgresql, pgbouncer, redis, rabbitmq),
  `docker-compose.backend.yml`, `docker-compose.frontend.yml`, `docker-compose.yml`, конфигурация
  pydantic-settings в `app/src/app/config/settings.py`.
- **Шаг 2** — выполнен: миграции alembic всех таблиц (`app/alembic/versions/`), доменные модели
  SQLAlchemy в `app/src/app/domain/models/`.
- **Шаг 3** — выполнен: внутренняя архитектура backend
  (`app/src/app/`):
  - `repository/` — базовый репозиторий + репозитории всех моделей (category, object, user,
    visitor, request, device, session, setting);
  - `services/` — `EventPublisher` (faststream/RabbitMQ: registration, request.created,
    request.cancelled), `TokenBlacklist` и `RateLimiter` (Redis), `AppSettingsService`
    (типизированный доступ к таблице settings);
  - `di/` — провайдеры dishka: settings, db (движок/сессии), redis, broker, repository,
    service; сборка контейнера `build_container()`;
  - `log.py` — логирование logging + structlog (console в debug, JSON в prod);
  - `api/main.py` — фабрика FastAPI (`create_app`), dishka (`setup_dishka`), CORS,
    health-роутер (`/api/v1/health`, `/api/v1/health/ready` — проверено TestClient).
- **Шаг 4** — выполнен: REST API (`app/src/app/api/`)
  - роутеры с `route_class=DishkaRoute`, зависимости через `FromDishka` (без `Depends`):
    - `auth` — login (rate-limit по IP), refresh (ротация refresh-токена), logout
      (оба токена в blacklist, деактивация сессии); access+refresh в httpOnly cookies
      (`ubc_access`, `ubc_refresh`);
    - `categories`, `objects` — CRUD + сортировка/активность; назначение менеджеров
      (`PUT /objects/{id}/managers`);
    - `pdf` — загрузка (`PUT /objects/{id}/pdf`, multipart, только PDF, ≤20МБ,
      файлы в `{PROJECT_DATA_DIR}/pdf/{object_id}/`), получение
      (`GET /objects/{id}/pdf`, inline, для авторизованных);
    - `users` — CRUD (admin; защита последнего admin, запрет самоудаления);
    - `visitors` — список/поиск/бан-разбан (admin);
    - `requests` — список (admin — все, менеджер — свои объекты), смена статуса
      (только менеджер объекта; переходы new→approved/rejected, approved→completed);
    - `devices`, `sessions` — списки с фильтром по пользователю, отзыв одной/всех сессий;
    - `settings` — чтение/обновление только известных ключей (admin);
  - авторизация через `AuthProvider` (dishka, REQUEST-scope): `User` по access-cookie
    с проверкой blacklist; `AdminUser` — обёртка для admin-only (403);
  - сервисы: `TokenService` (pyjwt), `AuthService` (bcrypt), `PdfService`;
  - зависимости добавлены: pyjwt, bcrypt, python-multipart; в `.env` — `BACKEND_JWT_SECRET`.
- **Шаг 5** — выполнен: бот (aiogram, `app/src/app/bot/`):
  - callback-схема — только классы `CallbackData` (`keyboards.py`):
    `CategoryCB`, `ObjectCB`, `ObjectActionCB`, `CreateRequestCB`, `RequestCB`,
    `ConsentCB`, `MenuCB`; клавиатуры с пагинацией ◀️ N/M ▶️;
  - хендлеры (`handlers/`): `registration` (/start: регистрация ФИО → телефон →
    согласие, блокировка, главное меню), `menu` (категории → объекты → страница
    объекта → PDF-документ Telegram), `requests` (создание заявки: телефон →
    комментарий; «Мои заявки» с пагинацией; отмена: new — всегда, approved —
    в пределах интервала из настроек);
  - `services.py` — `BotService` (REQUEST-scope, общая сессия БД): регистрация,
    меню, заявки, отмена, публикация событий;
  - DI (`di/bot.py`): `BotProvider` — `Bot` (APP, AiohttpSession с
    `BOT_PROXY_URL`) и `BotService` (REQUEST); `setup_dishka(container, dp)`,
    зависимости через `FromDishka`;
  - уведомления (`notifications.py`): консьюмеры RabbitMQ
    (notifications.registration → админы; notifications.request.created /
    request.cancelled → менеджеры объекта); если telegram_id не указан —
    пропуск (не ошибка); ошибки отправки не прерывают рассылку;
  - точка входа `main.py` (`python -m src.app.bot.main`): FSM в Redis
    (`RedisStorage`), dev — long-polling, prod — webhook
    (`BOT_WEBHOOK_BASE_URL`, secret, aiohttp-приложение для nginx);
  - настройки: `BOT_TOKEN`, `BOT_PROXY_URL`, `BOT_WEBHOOK_BASE_URL`,
    `BOT_WEBHOOK_PATH`, `BOT_WEBHOOK_SECRET`, `BOT_WEBHOOK_HOST`,
    `BOT_WEBHOOK_PORT`.
- **Шаг 6** — выполнен: frontend (Nuxt 3 + Tailwind, `frontend/`) + запуск
  всех приложений через docker-compose:
  - каркас: `nuxt.config.ts` (SPA, `@nuxtjs/tailwindcss`, `NUXT_PUBLIC_BACKEND_URL`),
    `Dockerfile` (node:22-alpine, build → `.output`), `assets/css/main.css`
    (btn/input/table/card утилиты);
  - composables: `useApi` ($fetch c `credentials: 'include'`, авто-refresh при 401,
    тип Page), `useAuth` (useState + localStorage, login/logout, isAdmin),
    `useDeviceId` (thumbmarkjs `getFingerprint`, кэш в localStorage),
    `useFormat` (UTC → Europe/Moscow);
  - `middleware/auth.global.ts` — /login для гостей, admin-only страницы
    (categories, objects, users, visitors, devices, sessions, settings);
  - `layouts/default.vue` — сайдбар (меню зависит от роли), выход;
  - компоненты: `UiModal`, `UiPagination`, `StatusBadge`;
  - страницы: `/login`, `/dashboard` (счётчики для админа), `/categories` (CRUD),
    `/objects` (CRUD, фильтр по категории, загрузка PDF ≤20МБ, открытие PDF
    в новой вкладке, назначение менеджеров), `/requests` (фильтры статус/объект/
    дата; подтверждение/отклонение/выполнение — менеджер), `/users` (CRUD,
    роль/telegram_id/активность), `/visitors` (поиск по ФИО, фильтр блокировки,
    бан/разбан), `/devices` (фильтр по пользователю), `/sessions` (фильтры,
    отзыв одной/всех), `/settings` (4 ключа: page_size, cancel_interval_hours,
    welcome_text, consent_text);
  - nginx (`srv/nginx/`): `nginx.conf` + `conf/default.conf` — reverse proxy
    `/api/` → backend:8000, `/bot/` → bot:8080 (webhook в prod), `/` →
    frontend:3000; client_max_body_size 25m (PDF);
  - запуск стека `docker compose up -d --build` — все 8 контейнеров работают
    (postgres, pgbouncer, redis, rabbitmq, nginx, backend, bot, frontend);
  - исправления при запуске: в `app/Dockerfile` копирование `src/` перенесено
    ДО `uv pip install -e .` (иначе editable-установка не находила пакет);
    добавлены `__init__.py` для `app/bot` и `app/bot/handlers`; в
    `app/pyproject.toml` — явный `[build-system]` (setuptools, packages в `src/`)
    и зависимость `aiohttp-socks` (SOCKS-прокси бота); в `di/broker.py` —
    `broker.stop()` вместо `close()` (faststream 0.7); в `notifications.py` —
    `routing_key` перенесён в `RabbitQueue` (API faststream 0.7);
  - проверено: миграции применены (все таблицы), admin создан, health
    (`/api/v1/health`, `/health/ready`) через nginx — ok, login admin с
    httpOnly cookies (2 cookie), авторизованные запросы (categories, users,
    settings), refresh — ok, frontend отдаёт SPA (200, lang="ru"), бот в
    long-polling с консьюмерами RabbitMQ (structlog: `bot_started_polling`);
  - доработки после запуска: тема Tailwind + `main.css` подключены в
    `nuxt.config.ts` (`css: [...]`), редирект `/` → `/dashboard`
    (`routeRules`), поле PDF в форме создания объекта, `FSInputFile` для
    отправки PDF ботом, `BACKEND_PDF_DATA_DIR` (общий volume backend/bot),
    `setup_dishka(..., auto_inject=True)`;
  - уведомления: имена очередей и routing keys вынесены в `.env`
    (`CONSUMER_QUEUE_*` / `CONSUMER_ROUTING_*`), добавлено событие
    `bot.notify.request.status` (смена статуса заявки → посетителю);
    брокер стартует ПОСЛЕ регистрации подписчиков (faststream 0.7).
- **Шаг 7** — актуализирован частично: unit + интеграционные тесты существуют
  и прогоняются в docker (`ubc-test-runner`, 211 passed); тесты диалога
  заявки (флаги, генераторы времени, RuCalendar, валидация/агрегация)
  добавлены в рамках доработки «Диалог создания заявки».
- **Шаг 8** — выполнен: итоговый документ проектирования `docs/architecture.md`
  (архитектура и компоненты, ER-модель, API-контракты, схема callback'ов и
  уведомлений бота, потоки данных, запуск и эксплуатация, известные
  особенности).
- **Диалог создания заявки (aiogram-dialog)** — выполнен:
  - флаги `requests.is_use_time_in_request` / `requests.is_use_end_date_in_request`
    в таблице settings (AppSettingsService + API + frontend `/settings`, чекбоксы);
  - миграции: `visitors.phone` (nullable) и `requests.start_date/start_time/
    end_date/end_time` (все nullable); модели SQLAlchemy обновлены;
  - телефон сохраняется при регистрации (`register_visitor(phone=...)`) и
    обновляется через `update_visitor_phone`; геттер `get_profile_phone`;
  - `aiogram-dialog` 2.6.0 добавлен в зависимости;
  - виджет `RuCalendar` (`bot/widgets/ru_calendar.py`) — подкласс `Calendar`
    с русскими названиями месяцев/дней недели, неделя с понедельника,
    min_date=сегодня, max_date=+2 года;
  - `RequestStates` — 8 состояний (input_phone … input_comment);
  - генераторы времени (`bot/dialogs/time_items.py`): часы 00–23, минуты
    с шагом 5;
  - диалог (`bot/dialogs/request_dialog.py`, 8 окон): телефон (профиль +
    MessageInput текст/контакт), RuCalendar для дат, Select в ScrollingGroup
    для часов/минут, комментарий; forward-роутинг по флагам start_data,
    backward-кнопки на вариативных шагах, валидация (end >= start, полные
    datetime при равных датах), финализация через `BotService.create_request`;
  - интеграция: старые FSM-хэндлеры создания заявки удалены, кнопка
    «Создать заявку» запускает `dialog_manager.start(...)` с флагами,
    `dp.include_router(request_dialog)` + `setup_dialogs(dp)` в `main.py`;
  - отображение дат/времени: `RequestOut` (API) дополнен полями
    `start_date/start_time/end_date/end_time`; frontend `/requests` — колонки
    «Начало»/«Окончание» (ДД.ММ.ГГГГ ЧЧ:ММ или «—»); карточка заявки в боте
    («Мои заявки») показывает строки «Начало»/«Окончание»;
  - тесты (unit + интеграционные, запуск в docker: `ubc-test-runner`):
    - unit: флаги настроек (default false, парсинг true/1/yes/on/да),
      генераторы времени (часы 00–23, минуты с шагом 5), тексты `RuCalendar`
      (месяцы/дни недели/заголовок), валидация и агрегация диалога
      (`validate_request_data`, `collect_request_data` по флагам);
    - интеграционные: фикстуры `visitor` (с `phone`) и `request_obj`
      (с датами/временем); `RequestOut` отдаёт новые поля (значения и null);
      флаги `is_use_...` в PUT/GET настроек;
    - прогон: 211 passed (unit + integration) в `ubc-test-runner`;
  - проверено: все контейнеры (backend, bot, frontend, nginx) подняты,
    бот в long-polling, health 200.
