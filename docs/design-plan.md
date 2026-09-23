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
- **manager** — управляет своими объектами (через таблицу связи объект↔менеджер) **и объектами своих категорий** (через таблицу связи категория↔менеджер), видит и обрабатывает заявки по доступным объектам.

Доступ менеджера к объекту определяется объединением:
- прямая связь в `object_managers`;
- связь с категорией объекта в `category_managers` (доступ ко **всем** объектам категории).

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
- **category_managers** — category_id (FK), user_id (FK), связь многие-ко-многим (доступ менеджера ко всем объектам категории)
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
- **categories**: CRUD + сортировка + флаг активности + назначение менеджеров
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
- **/categories** — категории (CRUD, сортировка, активность, назначение менеджеров, «Поля заявки»)
- **/objects** — объекты (CRUD, сортировка, активность, назначение менеджеров, загрузка PDF)
- **/fields** — справочник полей заявки (CRUD: код, тип, подпись, обязательность, meta_data)
- **/requests** — заявки (фильтры по статусу/объекту/дате; менеджер — свои, админ — все; подтверждение/отклонение менеджером; значения динамических полей)
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

## Доступ менеджера к категории (category_managers)

> Расширение модели доступа: менеджеру можно назначить категорию целиком,
> а не только отдельные объекты. Доступ к объекту = прямая связь ∪ связь
> через категорию объекта.

### Модель доступа

- **Прямая связь** — `object_managers` (как раньше): менеджер назначается
  на конкретный объект.
- **Связь через категорию** — `category_managers`: менеджер назначается
  на категорию и получает доступ ко **всем** объектам этой категории
  (заявки: просмотр и обработка; уведомления о новых/отменённых заявках).
- Итоговый список менеджеров объекта — объединение без дубликатов
  (`ObjectRepository.list_access_manager_ids`).
- Управление прямыми связями объекта (`GET/PUT /objects/{id}/managers`)
  показывает **только прямые** связи — чтобы редактирование не затирало
  связи, унаследованные от категории.

### Схема БД (миграция alembic)

- Новая таблица **category_managers**: id, category_id (FK → categories,
  CASCADE), user_id (FK → users, CASCADE); уникальный индекс
  `(category_id, user_id)`, индексы по обоим полям.
- Домен: `CategoryManager` (`app/src/app/domain/models/category_manager.py`),
  связи `Category.managers` ↔ `User.managed_categories`.

### Репозитории

- `CategoryRepository`: `add_manager` / `remove_manager` / `list_manager_ids`
  (прямые связи категории).
- `ObjectRepository`: `list_access_manager_ids(object_id)` — объединённый
  список менеджеров объекта (прямые ∪ категорийные); `list_manager_ids`
  остаётся списком только прямых связей.
- `RequestRepository.list_manager_object_ids(user_id)` — объекты прямых
  связей ∪ объекты категорий менеджера (видимость списка заявок).

### API

- **GET/PUT `/categories/{id}/managers`** (admin) — чтение/замена списка
  менеджеров категории (схемы `CategoryManagersIn/Out`).
- `POST /requests/{id}/status` — проверка доступа менеджера через
  `list_access_manager_ids` (прямо или через категорию объекта).
- Список/карточка заявок — через `list_manager_object_ids` (объединённый).

### Бот (уведомления)

- `BotService.create_request` / `cancel_request` — уведомления менеджерам
  по объединённому списку (`list_access_manager_ids`): менеджеры объекта
  напрямую + менеджеры категории объекта.

### Frontend

- `/categories` — кнопка «Менеджеры» и модалка назначения (по образцу
  объектов): чекбоксы активных менеджеров, PUT полного списка.

### Тесты

- Интеграционные: менеджеры категории (GET/PUT flow, unknown user 400,
  404); менеджер категории видит заявки по объектам категории и меняет
  их статус; `GET /objects/{id}/managers` — только прямые связи.

---

## Динамический конструктор заявок (настраиваемые поля)

> Расширение сценария заявок: админ настраивает для каждой категории набор
> полей заявки (тип, подпись, обязательность, порядок), бот строит диалог
> динамически по схеме из БД. Заменяет текущий фиксированный диалог
> (телефон → даты → комментарий) и глобальные флаги `is_use_*`.

### Анализ предложения (адаптация к текущей архитектуре)

Предложенный план принят за основу с исправлениями:

1. **Терминология**: проект использует `Request`/`requests` (не `order`) —
   таблицы называются `request_available_fields`, `request_category_fields`,
   `request_fields`; состояния — `DynamicRequestSG`.
2. **Телефон остаётся фиксированным**: `requests.phone` нужен менеджеру для
   связи, хранится в профиле посетителя (`visitors.phone`), отображается в
   «Моих заявках» и уведомлениях. Телефон собирается как сейчас (окно
   «номер из профиля»), динамические поля — дополнительные.
3. **Состояния по типу поля, а не по полю** — корректно: aiogram-dialog
   требует статического набора состояний; динамичность обеспечивается
   роутингом по `current_step` в массиве `schema`. Принято без изменений.
4. **Глобальные флаги `is_use_time_in_request` / `is_use_end_date_in_request`**
   устаревают: конфигурация дат/времени переходит в поля категории. Флаги
   удаляются из `ALLOWED_KEYS` API и чекбоксов `/settings` после перехода.
5. **Переиспользование**: `RuCalendar`, `generate_hours`/`generate_minutes`
   (шаг минут из `meta_data` вместо константы 5), паттерн
   `get_or_404`/`sync_managers` для API, `ensure_visitor` для бота.
6. **Добавлено к предложению** (в исходном плане отсутствует):
   - API управления полями (CRUD справочника + привязка к категории);
   - frontend: страница `/fields`, модалка настройки полей категории;
   - отображение значений полей: менеджерам в `/requests` (frontend) и
     посетителю в карточке «Мои заявки» (бот);
   - кнопки «Назад» между динамическими шагами (back-роутинг по
     `current_step - 1`, как в текущем диалоге);
   - валидация по типам: TEXT — длина из `meta_data`, NUMBER — min/max,
     SELECT — значение из списка опций; DATE/TIME проверяются виджетами.

### Принятые решения

- **A. Судьба старых колонок `requests.start_date/start_time/end_date/end_time`**
  и `requests.comment` — **Вариант 2 (решено)**: удалить колонки сразу в
  миграции конструктора; значения старых заявок по этим полям теряются
  (данные не переносятся в `request_fields`). `requests.phone` остаётся.
- **B. Хранение значений**: принято из предложения — универсальное
  `value_text` (String). Альтернатива (отдельные колонки
  text/number/date/time) — строже по типам, но сложнее в запросах;
  для текущих объёмов не требуется.
- **C. Миграция старых заявок**: значения старых колонок **не** переносятся
  в `request_fields` (следует из A — колонки удаляются сразу).

### Схема БД (миграция alembic)

1. **`request_available_fields`** — справочник полей:
   - `id` Integer PK;
   - `code` String(64) unique — тех. код (`delivery_time`);
   - `type` Enum(`tp_request_field_type`: text, number, date, time, select);
   - `label` String(255) — подпись для пользователя;
   - `is_required_default` Boolean;
   - `meta_data` JSONB nullable — опции SELECT (`{"options": ["Вариант 1", ...]}`),
     шаг минут TIME (`{"minute_step": 15}`), min/max NUMBER, max_length TEXT.
2. **`request_category_fields`** — привязка к категории:
   - `id` Integer PK;
   - `category_id` FK → categories (CASCADE);
   - `field_id` FK → request_available_fields (CASCADE);
   - `sort_order` Integer; `is_required` Boolean;
   - уникальный индекс `(category_id, field_id)`.
3. **`request_fields`** — значения полей заявки:
   - `id` Integer PK;
   - `request_id` FK → requests (CASCADE);
   - `field_id` FK → request_available_fields (RESTRICT — история заявок);
   - `value_text` String(1024) nullable (пропущенное обязательное — ошибка
     на этапе валидации диалога, в БД NULL не попадает);
   - уникальный индекс `(request_id, field_id)`, индекс по `request_id`.

Домен: `RequestFieldType` (enum), `RequestAvailableField`,
`RequestCategoryField`, `RequestField` (`app/src/app/domain/models/`),
связь `Request.values → request_fields`.

### FSM (бот)

Класс `DynamicRequestSG` (StatesGroup) — состояния по типу поля:

- `input_phone` (фиксированный первый шаг, как сейчас);
- `input_text`, `input_number`, `input_date`,
  `input_time_hour`, `input_time_minute`, `input_select`;
- `summary` — предпросмотр всех ответов + кнопка «Отправить».

Контекст диалога:

- `start_data["schema"]` — отсортированный список полей категории
  (dict: id, code, type, label, is_required, meta_data);
- `start_data["answers"]` — `{field_id: value_str}`;
- `dialog_data["current_step"]` — индекс текущего поля в schema;
- `dialog_data["temp_hour"]` — выбранный час между окнами TIME.

### Routing Engine (`bot/dialogs/dynamic_request_dialog.py`)

- `start_dynamic_order(manager)`: получить schema полей категории объекта
  (кэш в `start_data`), `current_step = 0`, `switch_to` по типу первого
  поля (пустая schema → сразу `summary`);
- `process_and_go_next(value)`: записать ответ, `current_step += 1`;
  конец схемы → `summary`; иначе `switch_to` по типу следующего поля
  (TIME — всегда на `input_time_hour`);
- `on_hour_selected`: `temp_hour = hour` → `input_time_minute`
  (без сдвига `current_step`);
- `on_minute_selected`: `f"{temp_hour}:{minute:02d}"` →
  `process_and_go_next(value)`;
- **Назад**: `Button` с `switch_to` по предыдущему полю
  (`current_step - 1`, TIME → `input_time_hour`); из телефона — выход
  (`manager.done()`).

### UI-слой (окна и геттеры)

Геттеры:

- `get_current_field_data` — label, is_required, meta_data поля по
  `current_step` (текст окна: подпись + пометка «обязательно»);
- `get_hours` / `get_minutes` — существующие генераторы, шаг минут из
  `meta_data["minute_step"]` (default 5);
- `get_select_options` — опции SELECT из `meta_data["options"]`;
- `get_summary` — список «label: value» по schema + answers.

Окна:

- `input_phone` — как сейчас (профиль + MessageInput);
- `input_text` / `input_number` — `MessageInput` + «Пропустить»
  (`when=not is_required`); NUMBER — валидация int + диапазон;
- `input_date` — `RuCalendar` (min_date=сегодня) + «Пропустить»;
- `input_time_hour` / `input_time_minute` — `Select` в `ScrollingGroup`,
  «Назад к часам» в окне минут;
- `input_select` — `Select` по опциям из `meta_data`;
- `summary` — `Format` сводки + «✅ Отправить» + «◀️ Назад»
  (к последнему полю схемы).

### Финализация

- `BotService.create_request(visitor, object_id, phone, values)`:
  создать `Request` (phone, object_id, status=new) + bulk-вставка
  `RequestField` по answers (одной транзакцией, как сейчас — сессия
  REQUEST-scope коммитится в DI), публикация `RequestCreatedEvent`;
- валидация обязательных полей до отправки (все answered или
  `is_required=False`), иначе возврат на первый пропущенный шаг.

### API

- `GET/POST /request-fields`, `PATCH/DELETE /request-fields/{id}` (admin) —
  CRUD справочника (`code`, `type`, `label`, `is_required_default`,
  `meta_data`);
- `GET/PUT /categories/{id}/fields` (admin) — привязка полей категории
  с `sort_order`/`is_required` (паттерн `sync_managers`: diff списков);
- `RequestOut` + `fields: list[RequestFieldValueOut]`
  (`{field_code, field_label, value}`) — значения полей в списке/карточке
  заявок (join по `request_fields`, eager-load чтобы избежать N+1);
- `RequestOut` больше **не** содержит `start_date/start_time/end_date/
  end_time/comment` (колонки удалены — решение A, вариант 2);
- frontend `/requests`: фильтры по датам (`date_from`/`date_to` →
  `requests.created_at` вместо удалённого `start_date`).

### Frontend

- Страница `/fields` (admin): CRUD справочника полей (код, тип, подпись,
  обязательность по умолчанию, meta_data — JSON-редактор/поля по типу);
- `/categories`: кнопка «Поля заявки» — модалка привязки полей к категории
  (чекбоксы + sort_order + is_required, PUT полного списка);
- `/requests`: отображение значений полей (карточка/расширяющаяся строка).

### Бот (отображение)

- Карточка заявки («Мои заявки»): строки значений полей
  (`label: value`) после телефона/статуса;
- Уведомления менеджерам — без изменений (событие уже содержит id заявки).

### Миграция настроек

- Из `ALLOWED_KEYS` API и `/settings` удалить
  `requests.is_use_time_in_request`, `requests.is_use_end_date_in_request`;
- из `AppSettingsService` удалить соответствующие геттеры;
- старый диалог `request_dialog.py` и `RequestStates` удалить.

### Тесты

Unit:

- схема полей: валидация meta_data по типам (SELECT без options → ошибка,
  TIME без minute_step → default 5);
- роутинг: `process_and_go_next` (конец схемы → summary, TIME →
  input_time_hour), назад по current_step;
- финализация: обязательные поля не отвечены → ошибка; ответы →
  values корректно агрегированы.

Интеграционные:

- API: CRUD полей, PUT полей категории (diff, unknown field 400),
  `RequestOut.fields` содержит значения; `RequestOut` не содержит
  `start_date/...`/`comment` (после миграции);
- БД: каскады (удаление категории → привязки; удаление заявки → значения;
  удаление поля с существующими значениями — RESTRICT);
- фикстуры: `request_with_fields` (заявка со значениями полей);
- обновить фикстуры `request_dates`/`request_obj` (данные заявок —
  через поля, а не колонки) и тесты `test_api_requests.py`.

### Порядок реализации (подзадачи)

1. Миграция alembic: 3 новые таблицы + удаление колонок
   `requests.start_date/start_time/end_date/end_time/comment` (решение A);
2. Домен: `RequestFieldType`, `RequestAvailableField`, `RequestCategoryField`,
   `RequestField`; правка модели `Request` (убрать колонки, связь values);
3. Репозитории: `RequestFieldRepository` (справочник + привязки + значения),
   обновить `RequestRepository` (фильтры дат → created_at);
4. API: роутер `request_fields` (+ привязки категорий), схемы, `RequestOut.fields`;
5. Бот: `DynamicRequestSG`, `dynamic_request_dialog.py` (routing engine,
   окна по типам), интеграция в `handlers/requests.py`; удаление старого
   диалога и `RequestStates`;
6. Настройки: удалить флаги `is_use_*` (ALLOWED_KEYS, AppSettingsService,
   frontend /settings);
7. Frontend: страница `/fields`, модалка полей категории, `/requests` —
   значения полей;
8. Тесты: unit + интеграционные (по списку выше), прогон в `ubc-test-runner`.

---

## Доступ менеджера к категориям и объектам (frontend)

**Статус: выполнено (23.09.2026).**

### Задача

Для пользователя с ролью `manager`:

1. в списке заявок в колонке «Объект» сейчас показывается **ID объекта**
   (`#12`) — нужно наименование объекта и ссылку на его карточку;
2. в главное меню добавить разделы **«Категории»** и **«Объекты»**;
3. раздел **«Дашборд»** — как у `admin`, но **без** карточки «Настройки».

### Причина ID вместо наименования (не баги вёрстки)

`frontend/pages/requests.vue` резолвит имя объекта локально:
`objectName(id)` ищет в списке, загруженном из `GET /objects?limit=1000`.
Этот эндпоинт — admin-only (`_admin: FromDishka[AdminUser]` в
`api/routers/objects.py`), менеджер получает **403**, запрос попадает в
`catch` (`console.warn('[requests] objects load failed')`), список остаётся
пустым и `objectName()` возвращает `` `#${id}` ``.

Вывод: без изменения прав backend задачу не решить — п.1 и п.2 требуют
одного и того же read-only доступа менеджера к категориям и объектам.

### Backend: read-only доступ менеджера

Логика видимости уже реализована в `ObjectRepository.list_manager_object_ids`
(прямые связи `object_managers` ∪ объекты категорий менеджера
`category_managers`) — переиспользуется без дублирования.

1. `GET /objects` — вместо `AdminUser` обычный `User`; для `manager`
   фильтрация по `list_manager_object_ids(user.id)` (total считает
   тот же фильтр), сортировка и пагинация без изменений.
2. `GET /objects/{id}` — для `manager` 404 при отсутствии объекта в
   доступных (тот же список).
3. `GET /categories` и `GET /categories/{id}` — для `manager` только
   категории, к которым у него есть доступ: категории доступных объектов
   ∪ категории, назначенные напрямую (`category_managers`). Новый метод
   `CategoryRepository.list_manager_category_ids(user_id)` по образцу
   объектного.
4. Все мутации остаются admin-only: `POST/PATCH/DELETE /objects`,
   `POST/PATCH/DELETE /categories`, `PUT /*/managers`,
   `PUT /request-fields/categories/{id}/fields`, загрузка PDF.
   Проверка — по факту `AdminUser` в зависимости эндпоинта.
5. `GET /objects/{id}/pdf` уже доступен любому авторизованному — без изменений.

### Frontend

1. **Меню** (`layouts/default.vue`): в `managerMenu` добавить
   `Категории` (`/categories`, icon `folder`) и `Объекты` (`/objects`,
   icon `cube`) между «Дашбордом» и «Заявками».
2. **Middleware** (`middleware/auth.global.ts`): убрать `/categories` и
   `/objects` из `ADMIN_ONLY` (остальное — `/fields`, `/users`,
   `/visitors`, `/devices`, `/sessions`, `/settings` — остаётся admin-only).
   Права на запись обеспечивает backend, frontend только скрывает кнопки.
3. **Колонка «Объект» в `/requests`**: наименование объекта +
   `NuxtLink` на карточку. Имя берётся из уже загруженного списка
   `/objects` (для менеджера он становится доступен), при отсутствии
   имени — прежний fallback `#{id}` (например, объект вне доступа).
4. **Карточка объекта** — два варианта открытия:
   - **A (предлагается)**: deep-link `/objects?open={id}` →
     `pages/objects.vue` читает `route.query.open`, открывает существующую
     модалку в режиме просмотра; минимум нового кода, единая страница
     списка;
   - **B**: отдельная страница `pages/objects/[id].vue` (полноценный
     роут карточки с PDF и описанием) — чище URL, но дублирует модалку
     и требует отдельной загрузки данных.
5. **Read-only режим для manager** на `/categories` и `/objects`: скрыть
   «Добавить», «Изменить», «Удалить», «Менеджеры», «Поля заявки»,
   загрузку PDF; оставить список, поиск/фильтры и просмотр (кнопка PDF —
   доступна, эндпоинт открыт).
6. **Дашборд** (`pages/dashboard.vue`): карточки показывать и менеджеру,
   исключив карточку «Настройки»; `counts` загружать для обеих ролей
   (после п.1–3 backend `/categories` и `/objects` отдают менеджеру его
   объёмы, `total` корректен); блок-заглушку «Вы вошли как менеджер» убрать.

### Тесты

- интеграционные (`app/tests/integration/`):
  - `manager` → `GET /objects` 200 и только свои объекты (прямые +
    через категорию), `total` соответствует фильтру;
  - `manager` → `GET /objects/{id}` 200 для своего, 404 для чужого;
  - `manager` → `GET /categories` 200 и только доступные категории,
    `GET /categories/{id}` 404 для чужой;
  - `manager` → `POST/PATCH/DELETE` объектов и категорий 403;
  - `admin` → видит все объекты и категории (существующие тесты не
    ломаются);
  - `GET /requests` остаётся с прежней видимостью (регрессия).
- frontend — ручная проверка в браузере под `manager`: наименование
  объекта вместо ID и переход по ссылке, пункты меню, дашборд без
  «Настроек», отсутствие кнопок CRUD.

### Порядок реализации

1. Backend: методы репозиториев + права read-only (с тестами);
2. применение миграций не требуется (правок схемы нет);
3. Frontend: middleware, меню, read-only режим, колонка «Объект»,
   deep-link карточки, дашборд;
4. прогон интеграционных тестов в `ubc-test-runner` (батчами), пересборка
   `ubc-app:latest` и `ubc-frontend:latest`, `docker restart ubc-nginx`
   после пересоздания backend (nginx кэширует IP upstream).

---

## Тюнинг: HTML в описании объекта и текст кнопки «Создать заявку»

**Статус: выполнено (23.09.2026).**

### 1. HTML в кратком описании объекта

**Проблема.** В форме объекта поле подписано «Краткое описание
(HTML/Markdown)», но в боте (`handlers/menu.py`) описание отправлялось
через `html.quote(obj.short_description)` с `parse_mode="HTML"` — весь
пользовательский текст экранировался, теги выводились буквально.

**Решение — только HTML (Markdown убирается).**

- санитизация — библиотека **`nh3`** (Rust `ammonia`, поддерживаемый
  преемник `bleach`), добавлена в зависимости (`app/pyproject.toml`);
  модуль `app/src/app/bot/html_sanitize.py`: whitelist тегов Telegram
  (`b, strong, i, em, u, ins, s, strike, del, code, pre, a, blockquote,
  tg-spoiler, br`) и атрибутов (`href`, `class` — ссылки,
  `expandable` — blockquote); недопустимые теги вырезаются (содержимое
  `<script>/<style>` удаляется целиком), текст экранируется;
- `handlers/menu.py`: описание отправляется как HTML **без экранирования**
  (разметку пишет пользователь); экранируются только служебные
  подстановки (`obj.name`);
- frontend `/objects`: подпись поля — «Краткое описание (HTML)»,
  подсказка с допустимыми тегами;
- Markdown не поддерживается (MarkdownV2 требует экранирования
  спецсимволов, автоопределение формата ненадёжно).

### 2. Текст кнопки «Создать заявку» — на уровне категории

- **Миграция `285f15deb694`**: `categories.button_text`
  (String(64), nullable) — NULL/пустое → текст по умолчанию
  «Создать заявку»; применена к основной и тестовой БД;
- **Домен**: `Category.button_text`;
- **API**: `CategoryIn/UpdateIn/Out` — новое поле; PATCH-семантика:
  `null` — не менять, `""` — сброс на дефолт;
- **Бот**: `object_keyboard(..., request_button_text=...)` — текст из
  категории объекта (`obj.category.button_text`), fallback «Создать
  заявку»; `ObjectRepository.get_with_category` (eager-load категории
  в `BotService.get_object`);
- **Frontend** `/categories`: поле «Текст для кнопки "Создать заявку"»
  с placeholder «Создать заявку» (пустое — дефолт).

### 3. Санитизация текстов настроек (доп. требование)

- `handlers/registration.py`: `welcome_text` и `consent_text`
  (вводятся админом в `/settings`) проходят `sanitize_html()` во всех
  местах вывода (4 точки); ФИО посетителя в сообщении экранируется
  `html.quote`;
- frontend `/settings`: подписи полей — «(HTML)», подсказка о
  допустимых тегах.

### 4. Исправления при тестировании (23.09.2026)

- **Двойная иконка в TIME-полях диалога заявки**: окна часов/минут
  (`dynamic_request_dialog.py`) — убраны «🕐» из текстов («Выберите
  час/минуты:»), иконка остаётся только в подписи поля из категории;
- **Кнопка «К объектам» возвращала на шаг заявки**: кнопка пакует
  `ObjectCB(category_id=X)` (без `object_id`), хендлера для такого
  callback не было — активный диалог aiogram-dialog перехватывал его.
  Добавлен хендлер `back_to_objects` в `handlers/menu.py` (список
  объектов категории с пагинацией, `ensure_visitor`);
- **Приветствие и меню сливаются**: вариант «двумя сообщениями» —
  `_show_main_menu` и `process_consent` отправляют приветствие
  отдельным сообщением (пустое — не отправляется), меню — отдельным
  (редактируется на месте при пагинации); при завершении регистрации
  сообщение согласия редактируется в «✅ Регистрация завершена, {ФИО}!»;
- **Настройки: `Input should be a valid string`**: `v-model` на
  `<input type="number">` отдаёт number, а `SettingsIn` требует
  `dict[str, str]` — frontend `settings.vue` приводит числовые поля к
  строке при отправке (`String(...)`), тип полей формы — `string | number`.

### Тесты

- unit: `test_html_sanitize.py` — 13 тестов (допустимые теги,
  вложенность, вырезание недопустимых, `<script>` — контент удаляется,
  экранирование текста и `href`, `<br>`, пустой ввод, примеры);
- интеграционные: `test_button_text_flow` (создание без текста → null,
  установка, null = не менять, `""` → сброс), `test_button_text_create`;
- прогон: 105 unit + 140 integration passed (батчами в
  `ubc-test-runner`); миграция тестовой БД через `db-update-test`;
- образы `ubc-app:latest`, `ubc-app-test:latest`, `ubc-frontend:latest`
  пересобраны; контейнеры backend/bot/frontend пересозданы, nginx
  перезапущен; health 200.

### 5. Unit-тест логики отмены заявок (can_cancel)

**Статус: выполнено (23.09.2026).** `tests/unit/test_can_cancel.py` —
на моках `app_settings` (без БД), 11 тестов:
- `new` → True; `rejected` / `completed` / `cancelled_by_customer` → False;
- `approved`: в пределах интервала → True, истёк → False,
  `confirmed_at is None` → False;
- граница: `now` ровно `confirmed_at + интервал` → True;
- интервал из настроек: 0 — отмена сразу недоступна; суб-часовой
  (30 мин: 20 — можно, 40 — нельзя); невалидное значение → дефолт 1440.

Далее интервал переведён с часов на минуты (см. справку ниже) —
тесты адаптированы; прогон: 117 unit + 15 integration passed.

### Использование интервала отмены (справка)

`requests.cancel_interval_minutes` (бывший `..._hours`, миграция
`4093e5d13bac` — ключ переименован, значение ×60) используется в
`BotService.can_cancel` (`app/src/app/bot/services.py`): статус `new` —
отмена всегда; статус `approved` — только пока
`now(UTC) <= confirmed_at + интервал`; иные статусы — нельзя.

**Семантика подтверждена (23.09.2026)**: интервал отсчитывается **от
момента подтверждения менеджером** (`confirmed_at` = `now(UTC)` при
`POST /requests/{id}/status` со статусом approved), а не от времени
заявки. Варианты привязки ко времени заявки (по динамическому полю
`visit_date`/`visit_time` — гибрид) отклонены. Тексты подсказок
(`/settings` helper, подпись поля) формулировать однозначно:
«сколько минут **после подтверждения** заявки менеджером посетитель
может её отменить».

**Тесты**: `tests/unit/test_app_settings.py` — геттер (дефолт 1440,
парсинг, невалидное/отрицательное → дефолт, 0 валиден);
`tests/unit/test_can_cancel.py` — логика отмены на моках настроек
(статусы new/rejected/completed/cancelled; approved в пределах
интервала / истёк / без confirmed_at; граница
`now == confirmed_at + интервал`; интервал 0, суб-часовой 30 мин,
невалид → дефолт 1440).

---

## Зависание полного прогона pytest с coverage

**Статус: закрыто (23.09.2026) — зависание не воспроизводится.**

### Симптом

- Пофайловые прогоны проходят полностью: unit — 89 passed, интеграционные
  батчами — 34 + 27 + 43 + 86 passed (итого 279 тестов);
- полный прогон `pytest --cov=src` в одной сессии зависает на ~33%
  (начало интеграционных тестов) — >9 мин без прогресса;
- без `--cov` те же файлы в тех же батчах проходят;
- ранее такое зависание уже наблюдалось и было объяснено (см. раздел
  «Динамический конструктор заявок — реализация», исправления 20.09.2026):
  фикстура `_cleanup_db` делает `TRUNCATE ... RESTART IDENTITY CASCADE`
  (ACCESS EXCLUSIVE, без `lock_timeout`) и вечно ждёт, если в тестовой БД
  есть незавершённая транзакция или параллельный прогон.

### Особенности текущего случая

- параллельных прогонов не было (проверено `pg_stat_activity` — висящих
  TRUNCATE не зафиксировано в момент зависания);
- зависание воспроизводится именно при полном прогоне ВСЕХ интеграционных
  тестов в одной сессии; те же файлы по отдельности/батчами < 2 мин не виснут;
- `pytest-timeout` (`timeout = 120`) в `app/pyproject.toml` не срабатывает:
  метод `signal` не прерывает блокировку внутри `TRUNCATE` в фикстуре,
  если сигнал доставлен в момент ожидания блокировки БД (ждёт libpq-сокет,
  Python-код не выполняется).

### Гипотезы

1. Соединение с незакрытой транзакцией из раннего интеграционного теста
   (ошибка сериализации/ DI-скоупа после формирования ответа) — TRUNCATE
   следующего теста ждёт его вечно; при батчах «виновник» просто не попадает
   в тот же прогон.
2. Взаимодействие coverage-трассировки с таймингами (замедление) — маскирует
   или провоцирует гонку в фикстурах.
3. Исчерпание пула соединений test-движка при полном прогоне (second pool +
   DI-сессии) — взаимоблокировка на уровне пула, а не БД.

### План диагностики

1. `docker compose -f docker-compose.test.yml up test-runner` (или штатный
   способ запуска тестов) — полный прогон с `--cov` и параллельно
   `SELECT pid, state, wait_event_type, wait_event, xact_start, left(query,80)
   FROM pg_stat_activity WHERE datname = '<test_db>'` — зафиксировать, кто
   кого блокирует в момент зависания;
2. прогон с `-v` (по одному имени теста в логе) — определить ТОЧНУЮ позицию
   зависания (пока известно только ~33%);
3. бисекция: добавить половину интеграционных файлов к unit — сузить
   «виновника»;
4. проверить `tests/integration/conftest.py`: порядок фикстур
   (`_cleanup_db` относительно client/engine), явный `engine.dispose()` /
   `commit/rollback` в финализаторах.

### Варианты исправления (по итогам диагностики)

- `SET lock_timeout` (например 10 с) перед TRUNCATE в `_cleanup_db` —
  зависание превратится в явную ошибку с трассировкой;
- гарантированное завершение транзакций DI-сессий в фикстуре клиента
  (shutdown hook вместо DI ExitError);
- отдельная тестовая БД на батч (если причина — перекрёстное влияние);
- `pytest-timeout` с методом `thread` вместо `signal`.

### Временное решение (было принято до закрытия)

- тесты гонять батчами (проходят);
- coverage замерять только по unit-тестам:
  `pytest tests/unit --cov=src --cov-report=term-missing`.

### Итог диагностики (23.09.2026) — закрыто

Полный прогон `pytest tests/unit tests/integration --cov=src` в
`ubc-test-runner`: **257 passed за 3 мин 16 с**, EXIT=0, coverage 68%
(2767 stmts / 883 miss). Зависание не воспроизведено; блокировок
TRUNCATE не было — фикстура `_cleanup_db` с `lock_timeout=5s` /
`statement_timeout=30s` отработала без ошибок во всех интеграционных
тестах.

Причины, устранившие проблему (изменения 20–23.09.2026):
- `_cleanup_db` защищён таймаутами (`SET LOCAL lock_timeout/statement_timeout`
  в транзакции очистки) — блокировка превращается в явную ошибку
  теста (`RuntimeError` с трассировкой), а не зависание прогона;
- исправлены ошибки DI-скоупов, провоцировавшие незавершённые
  транзакции (`flush` в `DELETE /request-fields`, eager-load значений
  заявки и др.);
- `pytest-timeout` (120 с, метод signal) — страховка.

Временные ограничения сняты: полный прогон с `--cov` в одной сессии
разрешён. Шаги 2–4 плана диагностики (прогон `-v`, бисекция, разбор
conftest) отменены как избыточные. При повторном зависании —
`lock_timeout` даст явную ошибку с трассировкой виновника.

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
- **Шаг 7** — выполнен: unit + интеграционные тесты прогоняются в docker
  (`ubc-test-runner`): 89 unit + 129 integration = **218 passed** (полный прогон
  `pytest` без `-x`, ~3 мин). Покрыты: валидаторы, сервисы (токены, PDF, пароли,
  настройки), схемы, генераторы времени, `RuCalendar`, роутинг динамического
  диалога заявки, репозитории и весь REST API (auth, categories, objects, pdf,
  users, visitors, requests, request-fields, sessions, devices, settings).
  Защита от зависания прогона — `pytest-timeout` (`timeout = 120`).
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
- **Доступ менеджера к категории (category_managers)** — выполнен:
  - миграция `c37575650d4b` (таблица `category_managers`), домен
    `CategoryManager` + связи `Category.managers`/`User.managed_categories`;
  - репозитории: `CategoryRepository.add/remove/list_manager_ids`,
    `ObjectRepository.list_access_manager_ids` (прямые ∪ категорийные),
    `RequestRepository.list_manager_object_ids` (объединённый);
  - API: `GET/PUT /categories/{id}/managers` (admin, схемы
    `CategoryManagersIn/Out`); `POST /requests/{id}/status` — доступ
    через объект или категорию объекта; список заявок менеджера —
    по объединённому набору объектов;
  - бот: уведомления о новых/отменённых заявках — объединённый список
    менеджеров объекта и категории объекта;
  - frontend: `/categories` — кнопка «Менеджеры» + модалка назначения;
  - тесты: 103 unit + 116 integration passed (прогон в `ubc-test-runner`,
    миграция тестовой БД через `db-update-test`).
- **Code review (безопасность/дублирование/эффективность)** — выполнен:
  38 пунктов исправлены (fail-fast JWT, scram-sha-256, атомарный rate-limit,
  ManagerLinkMixin, get_or_404, PATCH-семантика и др.) — отчёт и статусы:
  `docs/code-review-report.md`; тесты: 107 unit + 116 integration passed.
- **Динамический конструктор заявок (настраиваемые поля)** — план в разделе
  «Динамический конструктор заявок» выше. Решения приняты: A — вариант 2
  (старые колонки `start_date/start_time/end_date/end_time/comment` удаляются
  сразу, значения старых заявок теряются); B — хранение `value_text`;
  C — значения старых заявок не переносятся.
- **Динамический конструктор заявок — реализация (19–20.09.2026)** — выполнено:
  - миграции `6ff1993df41c` (request_available_fields), `ddc4dbf735eb`
    (request_category_fields), `b17f420b729b` (request_fields),
    `8f72ad889d7c` (удаление старых колонок requests) — применены к основной
    и тестовой БД (head = `8f72ad889d7c`);
  - правило: в миграциях `sa.Enum` только с классом модели — в `6ff1993df41c`
    исправлено на `sa.Enum(RequestFieldType, name="tp_request_field_type",
    values_callable=...)`, откат до `c37575650d4b` и повторный upgrade
    выполнены (обе БД); метки в БД: text/number/date/time/select;
  - модель `meta_data` приведена к `JSONB` (расхождение model/DB устранено,
    `alembic check` расхождений типов не показывает);
  - домен: `RequestFieldType`, `RequestAvailableField`, `RequestCategoryField`,
    `RequestField`; у `Request` удалены `comment/start_date/start_time/
    end_date/end_time`, добавлена связь `values` (`lazy="selectin"`);
  - репозитории: `RequestFieldRepository` (справочник, привязки категорий,
    значения заявок, `count_request_values`), `RequestRepository.get_with_values`
    и `list_page` — eager-load значений вместе со справочником поля;
  - API: `/request-fields` (CRUD, валидация `meta_data` по типу),
    `GET/PUT /request-fields/categories/{id}/fields` (diff-замена состава),
    `RequestOut.fields`; `DELETE /request-fields/{id}` — 400 при наличии
    значений заявок (FK RESTRICT);
  - бот: `DynamicRequestSG` + `bot/dialogs/dynamic_request_dialog.py`
    (routing engine, окна по типам полей, summary, финализация через
    `BotService.create_request(values=...)`); карточка «Мои заявки» показывает
    значения полей; старый `request_dialog.py`, `RequestStates` и флаги
    `is_use_*` удалены (`ALLOWED_KEYS`, `AppSettingsService`, `/settings`);
  - frontend: страница `/fields` (CRUD справочника), `/categories` — модалка
    «Поля заявки», `/requests` — значения полей и фильтр по `created_at`;
  - **исправления 20.09.2026 (найденные при прогоне тестов)**:
    - `MissingGreenlet` в 7 тестах `test_api_requests.py`: `RequestOut.fields`
      строится из `value.field.code/label`, а `RequestField.field` грузился
      лениво вне async-контекста. Добавлены
      `RequestRepository.get_with_values()` и
      `selectinload(Request.values).selectinload(RequestField.field)` в
      `list_page`; роутер заявок читает заявки только через `get_with_values`;
    - `DELETE /request-fields/{id}`: `session.delete()` не выполняет flush,
      IntegrityError (FK RESTRICT) всплывал на `commit` в `di/db.py` уже после
      формирования ответа (dishka ExitError вместо 400). Добавлены
      предварительная проверка `count_request_values()` и `flush()` внутри
      try/except → корректный 400;
    - **зависание полного прогона pytest** (>15 мин) не воспроизводится после
      исправления падений: `pytest` целиком — 218 passed за ~3 мин.
      Механизм блокировки: фикстура `_cleanup_db` выполняет
      `TRUNCATE ... RESTART IDENTITY CASCADE` (ACCESS EXCLUSIVE lock, `lock_timeout`
      не задан → ждёт вечно). Блокирует либо соединение с незавершённой
      транзакцией (ошибка после выхода из DI-скоупа — при сериализации ответа,
      сессия не коммитится/не закрывается), либо **параллельный прогон pytest** в
      той же тестовой БД (проверено: два одновременных прогона дают
      `2 failed, 211 passed, 5 errors` и активные `TRUNCATE` в
      `pg_stat_activity`). Правила прогона: один прогон одновременно; после
      обрыва `docker exec` проверять `docker top ubc-test-runner` и убивать
       оставшийся pytest; при подозрении на блокировку смотреть
       `pg_stat_activity` (`state`, `wait_event`, `xact_age`);
     - подключен `pytest-timeout`: dev-зависимость + `timeout = 120`
       (`app/pyproject.toml`, метод signal) — висящий тест прерывается вместо
       бесконечного ожидания (проверено: тест со `sleep(60)` при `--timeout=3`
       завершён за 3 с); образ `ubc-app-test` пересобран;
  - тесты: unit — `meta_data` по типам, роутинг (`process_and_go_next`,
    `go_back`, `_after_phone`), финализация; интеграционные — CRUD справочника,
    привязки категории, `RequestOut.fields`, RESTRICT при удалении;
  - прогон в `ubc-test-runner` (полный `pytest` без `-x`): **218 passed**
    (89 unit + 129 integration), 3 мин; образы `ubc-app` и `ubc-app-test`
    пересобраны, контейнеры backend/bot/test-runner пересозданы.
- **Доступ менеджера к категориям и объектам (frontend)** — выполнено
  (23.09.2026):
  - backend: `app/src/app/api/access.py` — общие хелперы
    `visible_object_ids` / `visible_category_ids` (admin → `None` = без
    фильтрации; менеджер → список доступных); `GET /objects`,
    `GET /objects/{id}`, `GET /categories`, `GET /categories/{id}` — вместо
    `AdminUser` обычный `User`, менеджеру отдаются только доступные
    (404 для чужих, пустой список без назначений); все мутации (POST/PATCH/
    DELETE, PUT /*/managers, загрузка PDF, поля категории) — по-прежнему
    admin-only (`AdminUser`);
  - `CategoryRepository.list_manager_category_ids(user_id)` — категории,
    назначенные напрямую (`category_managers`) ∪ категории объектов
    с прямой связью (`object_managers`);
  - frontend: middleware — `/categories` и `/objects` убраны из
    `ADMIN_ONLY`; меню менеджера — добавлены «Категории» и «Объекты»;
    `/requests` — колонка «Объект»: наименование + ссылка
    `NuxtLink` на `/objects?open={id}` (fallback `#{id}` при недоступном
    объекте); `/objects` — deep-link `?open={id}` (модалка карточки
    в режиме просмотра) и read-only режим менеджера (поля disabled,
    «Открыть PDF», скрыты «Добавить»/«Изменить»/«Удалить»/«Менеджеры»);
    `/categories` — read-only (скрыты кнопки действий и колонка
    «Действия»); `/dashboard` — карточки-счётчики для обеих ролей
    (у менеджера без «Настроек»), заглушка «Вы вошли как менеджер»
    убрана;
  - тесты: 92 unit + 138 integration passed (прогон в `ubc-test-runner`
    батчами: репозитории/категории/объекты — 44, auth/users/visitors — 38,
    requests/request-fields/pdf — 36, sessions/devices/settings — 20);
    новые интеграционные: менеджер без назначений — пустой список/404,
    прямая связь объекта и назначение категории — видимость, запись — 403;
    репозитории — `list_manager_object_ids`, `list_manager_category_ids`,
    `list_access_manager_ids` (прямые ∪ категорийные);
  - образы `ubc-app:latest`, `ubc-app-test:latest`, `ubc-frontend:latest`
    пересобраны; контейнеры backend/bot/frontend пересозданы, nginx
    перезапущен; health 200, frontend отвечает.
- **Тюнинг: HTML в описании объекта и текст кнопки «Создать заявку»** —
  выполнено (23.09.2026). Подробности — в разделе «Тюнинг» выше.
  Кратко:
  - санитизация HTML (библиотека `nh3`) для описания объекта и текстов
    настроек (welcome/consent) при выводе в боте; описание — HTML без
    экранирования (разметку пишет пользователь), whitelist тегов
    Telegram; Markdown убран (подпись поля — «(HTML)»);
  - миграция `285f15deb694`: `categories.button_text` (текст кнопки
    «Создать заявку» на уровне категории), домен, API
    (`CategoryIn/UpdateIn/Out`, PATCH: null — не менять, `""` — сброс),
    бот (`object_keyboard(request_button_text=...)`,
    `ObjectRepository.get_with_category`), frontend — поле в форме
    категории;
  - исправления по результатам ручного тестирования: двойная иконка
    🕐 в TIME-окнах диалога, кнопка «К объектам» (новый хендлер
    `back_to_objects` — раньше callback перехватывал активный диалог),
    приветствие и меню — разными сообщениями, настройки — приведение
    числовых полей к строке при PUT (`Input should be a valid string`);
  - тесты: unit `test_html_sanitize.py` (13), интеграционные
    `button_text` (flow + create); прогоны: 105 unit + 140
    integration passed (батчами); миграция тестовой БД
    `db-update-test`; образы пересобраны, контейнеры пересозданы,
    nginx перезапущен, health 200.

