"""Сервис бота: регистрация посетителей, меню, заявки, отмена."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Category, Object, Request, RequestStatus, Visitor
from app.domain.models.request_field_value import VALUE_TEXT_MAX_LENGTH
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository
from app.repository.request import RequestRepository
from app.repository.request_field import RequestFieldRepository
from app.repository.visitor import VisitorRepository
from app.services.app_settings import AppSettingsService
from app.services.events import EventPublisher, RequestCancelledEvent, RequestCreatedEvent, VisitorRegisteredEvent


class BotServiceError(Exception):
    """Ошибка бизнес-логики бота (показывается пользователю)."""


def _clamp_page(page: int, pages: int) -> int:
    """Номер страницы в пределах 0..pages-1 (подделанный/устаревший callback)."""
    return min(max(page, 0), pages - 1)


def _pages(total: int, page_size: int) -> int:
    return max(1, -(-total // page_size))


class BotService:
    """Бизнес-логика бота (REQUEST-scope, общая сессия БД)."""

    def __init__(
        self,
        session: AsyncSession,
        visitors: VisitorRepository,
        categories: CategoryRepository,
        objects: ObjectRepository,
        requests: RequestRepository,
        request_fields: RequestFieldRepository,
        app_settings: AppSettingsService,
        publisher: EventPublisher,
    ) -> None:
        self.session = session
        self.visitors = visitors
        self.categories = categories
        self.objects = objects
        self.requests = requests
        self.request_fields = request_fields
        self.app_settings = app_settings
        self.publisher = publisher
        # кеш посетителя в пределах обновления (middleware, хендлер, диалог)
        self._visitor_cache: dict[int, Visitor | None] = {}

    # -- регистрация --------------------------------------------------------

    async def get_visitor(self, telegram_id: int) -> Visitor | None:
        """Посетитель по telegram_id (один запрос на обновление)."""
        if telegram_id not in self._visitor_cache:
            self._visitor_cache[telegram_id] = await self.visitors.get_by_telegram_id(
                telegram_id
            )
        return self._visitor_cache[telegram_id]

    async def get_active_visitor(self, telegram_id: int) -> Visitor:
        """Зарегистрированный незаблокированный посетитель (или BotServiceError)."""
        visitor = await self.get_visitor(telegram_id)
        if visitor is None:
            raise BotServiceError("Сначала завершите регистрацию (/start).")
        if visitor.is_blocked:
            raise BotServiceError("Вы заблокированы.")
        return visitor

    async def register_visitor(
        self, telegram_id: int, full_name: str, phone: str | None = None
    ) -> Visitor:
        """Завершить регистрацию: согласие уже дано (вызывается после consent).

        phone — номер, введённый на шаге регистрации (сохраняется в профиле).
        """
        visitor = await self.visitors.get_by_telegram_id(telegram_id)
        now = datetime.now(timezone.utc)
        if visitor is None:
            visitor = Visitor(
                telegram_id=telegram_id,
                full_name=full_name,
                phone=phone,
                consent_given=True,
                consent_at=now,
            )
            await self.visitors.add(visitor)
        else:
            visitor.full_name = full_name
            if phone is not None:
                visitor.phone = phone
            visitor.consent_given = True
            visitor.consent_at = now
        await self.session.flush()
        self._visitor_cache[telegram_id] = visitor
        await self.publisher.publish_visitor_registered(
            VisitorRegisteredEvent(
                visitor_id=visitor.id,
                telegram_id=telegram_id,
                full_name=full_name,
            )
        )
        return visitor

    async def get_profile_phone(self, telegram_id: int) -> str | None:
        """Сохранённый телефон посетителя (для диалога заявки)."""
        visitor = await self.get_visitor(telegram_id)
        return visitor.phone if visitor is not None else None

    async def update_visitor_phone(self, telegram_id: int, phone: str) -> None:
        """Обновить телефон в профиле (при вводе нового номера в диалоге заявки)."""
        visitor = await self.get_visitor(telegram_id)
        if visitor is None:
            raise BotServiceError("Посетитель не найден")
        visitor.phone = phone
        await self.session.flush()

    # -- меню ---------------------------------------------------------------

    async def list_categories(self, page: int) -> tuple[list[Category], int, int]:
        """Страница активных категорий: (элементы, всего страниц, номер страницы).

        Номер страницы ограничивается диапазоном 0..pages-1.
        """
        page_size = await self.app_settings.get_page_size()
        total = await self.categories.count(Category.is_active.is_(True))
        pages = _pages(total, page_size)
        page = _clamp_page(page, pages)
        items = await self.categories.list_active(limit=page_size, offset=page * page_size)
        return list(items), pages, page

    async def list_objects(
        self, category_id: int, page: int
    ) -> tuple[list[Object], int, int]:
        """Страница активных объектов активной категории: (элементы, страниц, номер)."""
        page_size = await self.app_settings.get_page_size()
        total = await self.objects.count(
            *self.objects.active_conditions(category_id)
        )
        pages = _pages(total, page_size)
        page = _clamp_page(page, pages)
        items = await self.objects.list_by_category(
            category_id, only_active=True, limit=page_size, offset=page * page_size
        )
        return list(items), pages, page

    async def get_object(self, object_id: int) -> Object | None:
        """Активный объект активной категории (вместе с категорией — для текста кнопки)."""
        obj = await self.objects.get_with_category(object_id)
        if obj is not None and obj.is_active and obj.category.is_active:
            return obj
        return None

    async def save_pdf_file_id(
        self, object_id: int, pdf_path: str, file_id: str
    ) -> None:
        """Сохранить file_id отправленного PDF (только если PDF не заменён)."""
        await self.session.execute(
            update(Object)
            .where(Object.id == object_id, Object.pdf_path == pdf_path)
            .values(telegram_file_id=file_id)
        )

    # -- заявки -------------------------------------------------------------

    async def get_category_schema(self, object_id: int) -> list[dict]:
        """Схема полей заявки для категории объекта (для динамического диалога).

        Возвращает список dict: id, code, type, label, is_required, meta_data
        в порядке sort_order. Пустой список — категория без полей.
        """
        obj = await self.get_object(object_id)
        if obj is None:
            raise BotServiceError("Объект не найден")
        rows = await self.request_fields.list_category_fields(obj.category_id)
        return [
            {
                "id": f.id,
                "code": f.code,
                "type": f.type.value,
                "label": f.label,
                "is_required": link.is_required,
                "meta_data": f.meta_data or {},
            }
            for link, f in rows
        ]

    async def get_request_values(self, request_id: int) -> list[tuple[str, str | None]]:
        """Значения полей заявки (label, value) — для карточки «Мои заявки».

        Один путь чтения значений — RequestRepository.get_with_values.
        """
        req = await self.requests.get_with_values(request_id)
        if req is None:
            return []
        values = sorted(req.values, key=lambda v: v.field_id)
        return [(v.field.label, v.value_text) for v in values]

    async def create_request(
        self,
        visitor: Visitor,
        object_id: int,
        phone: str,
        values: dict[int, str | None],
    ) -> Request:
        """Создать заявку (статус «новая») с динамическими полями
        и уведомить менеджеров объекта.

        values — {field_id: value_text} по схеме полей категории объекта.
        Вставка выполняется (flush) до публикации события: ошибка БД не
        приводит к уведомлению о несуществующей заявке.
        """
        obj = await self.get_object(object_id)
        if obj is None:
            raise BotServiceError("Объект не найден")
        too_long = [
            field_id
            for field_id, value in values.items()
            if value is not None and len(value) > VALUE_TEXT_MAX_LENGTH
        ]
        if too_long:
            raise BotServiceError(
                f"Слишком длинное значение поля (максимум {VALUE_TEXT_MAX_LENGTH} символов)."
            )
        req = Request(
            visitor_id=visitor.id,
            object_id=object_id,
            phone=phone,
            status=RequestStatus.NEW,
        )
        await self.requests.add(req)
        # динамические поля заявки (одна транзакция с заявкой)
        if values:
            await self.request_fields.add_values(req.id, values)
        await self.session.flush()
        # менеджеры объекта напрямую + менеджеры категории объекта
        manager_ids = await self.objects.list_access_manager_ids(object_id)
        # фиксация до публикации: консьюмер не получит событие о заявке,
        # которой нет в БД
        await self.session.commit()
        await self.publisher.publish_request_created(
            RequestCreatedEvent(
                request_id=req.id,
                object_id=object_id,
                object_name=obj.name,
                manager_ids=manager_ids,
                visitor_telegram_id=visitor.telegram_id,
            )
        )
        return req

    async def list_visitor_requests(
        self, visitor_id: int, page: int
    ) -> tuple[list[Request], int, int]:
        """Страница заявок посетителя: (элементы, всего страниц, номер страницы)."""
        page_size = await self.app_settings.get_page_size()
        total = await self.requests.count(Request.visitor_id == visitor_id)
        pages = _pages(total, page_size)
        page = _clamp_page(page, pages)
        items = await self.requests.list_by_visitor(
            visitor_id, limit=page_size, offset=page * page_size
        )
        return list(items), pages, page

    async def get_request(
        self, request_id: int, visitor_id: int, *, for_update: bool = False
    ) -> Request | None:
        """Заявка посетителя (только своя); for_update — с блокировкой строки."""
        if for_update:
            req = await self.requests.get_for_update(request_id)
        else:
            req = await self.requests.get(request_id)
        if req is None or req.visitor_id != visitor_id:
            return None
        return req

    async def can_cancel(self, req: Request) -> bool:
        """Можно ли отменить заявку: new — всегда, approved — в пределах интервала."""
        if req.status == RequestStatus.NEW:
            return True
        if req.status == RequestStatus.APPROVED and req.confirmed_at is not None:
            minutes = await self.app_settings.get_cancel_interval_minutes()
            deadline = req.confirmed_at + timedelta(minutes=minutes)
            return datetime.now(timezone.utc) <= deadline
        return False

    async def cancel_request(self, req: Request) -> Request:
        """Отменить заявку посетителя и уведомить менеджеров.

        req должна быть прочитана с блокировкой (get_request(for_update=True)):
        переход проверяется по актуальному статусу, параллельная смена статуса
        менеджером ждёт завершения транзакции.
        """
        if not await self.can_cancel(req):
            raise BotServiceError("Заявку нельзя отменить")
        req.status = RequestStatus.CANCELLED_BY_CUSTOMER
        # менеджеры объекта напрямую + менеджеры категории объекта
        manager_ids = await self.objects.list_access_manager_ids(req.object_id)
        await self.session.commit()
        await self.publisher.publish_request_cancelled(
            RequestCancelledEvent(
                request_id=req.id,
                object_id=req.object_id,
                manager_ids=manager_ids,
            )
        )
        return req
