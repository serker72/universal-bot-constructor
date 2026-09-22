"""Сервис бота: регистрация посетителей, меню, заявки, отмена."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Category, Object, Request, RequestStatus, Visitor
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository
from app.repository.request import RequestRepository
from app.repository.request_field import RequestFieldRepository
from app.repository.visitor import VisitorRepository
from app.services.app_settings import AppSettingsService
from app.services.events import EventPublisher, RequestCancelledEvent, RequestCreatedEvent, VisitorRegisteredEvent


class BotServiceError(Exception):
    """Ошибка бизнес-логики бота (показывается пользователю)."""


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

    # -- регистрация --------------------------------------------------------

    async def get_visitor(self, telegram_id: int) -> Visitor | None:
        """Посетитель по telegram_id."""
        return await self.visitors.get_by_telegram_id(telegram_id)

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
        visitor = await self.visitors.get_by_telegram_id(telegram_id)
        return visitor.phone if visitor is not None else None

    async def update_visitor_phone(self, telegram_id: int, phone: str) -> None:
        """Обновить телефон в профиле (при вводе нового номера в диалоге заявки)."""
        visitor = await self.visitors.get_by_telegram_id(telegram_id)
        if visitor is None:
            raise BotServiceError("Посетитель не найден")
        visitor.phone = phone
        await self.session.flush()

    # -- меню ---------------------------------------------------------------

    async def list_categories(self, page: int) -> tuple[list[Category], int]:
        """Страница активных категорий и общее число страниц."""
        page_size = await self.app_settings.get_page_size()
        items = await self.categories.list_active(limit=page_size, offset=page * page_size)
        total = await self.categories.count(Category.is_active.is_(True))
        pages = max(1, -(-total // page_size))
        return list(items), pages

    async def list_objects(
        self, category_id: int, page: int
    ) -> tuple[list[Object], int]:
        """Страница активных объектов категории и общее число страниц."""
        page_size = await self.app_settings.get_page_size()
        items = await self.objects.list_by_category(
            category_id, only_active=True, limit=page_size, offset=page * page_size
        )
        total = await self.objects.count(
            Object.category_id == category_id, Object.is_active.is_(True)
        )
        pages = max(1, -(-total // page_size))
        return list(items), pages

    async def get_object(self, object_id: int) -> Object | None:
        """Активный объект по id."""
        obj = await self.objects.get(object_id)
        if obj is not None and obj.is_active:
            return obj
        return None

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
        """Значения полей заявки (label, value) — для карточки «Мои заявки»."""
        rows = await self.request_fields.list_values(request_id)
        return [(f.label, v.value_text) for v, f in rows]

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
        """
        obj = await self.get_object(object_id)
        if obj is None:
            raise BotServiceError("Объект не найден")
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
        # менеджеры объекта напрямую + менеджеры категории объекта
        manager_ids = await self.objects.list_access_manager_ids(object_id)
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
    ) -> tuple[list[Request], int]:
        """Страница заявок посетителя."""
        page_size = await self.app_settings.get_page_size()
        items = await self.requests.list_by_visitor(
            visitor_id, limit=page_size, offset=page * page_size
        )
        total = await self.requests.count(Request.visitor_id == visitor_id)
        pages = max(1, -(-total // page_size))
        return list(items), pages

    async def get_request(self, request_id: int, visitor_id: int) -> Request | None:
        """Заявка посетителя (только своя)."""
        req = await self.requests.get(request_id)
        if req is None or req.visitor_id != visitor_id:
            return None
        return req

    async def can_cancel(self, req: Request) -> bool:
        """Можно ли отменить заявку: new — всегда, approved — в пределах интервала."""
        if req.status == RequestStatus.NEW:
            return True
        if req.status == RequestStatus.APPROVED and req.confirmed_at is not None:
            hours = await self.app_settings.get_cancel_interval_hours()
            deadline = req.confirmed_at + timedelta(hours=hours)
            return datetime.now(timezone.utc) <= deadline
        return False

    async def cancel_request(self, req: Request) -> Request:
        """Отменить заявку посетителя и уведомить менеджеров."""
        if not await self.can_cancel(req):
            raise BotServiceError("Заявку нельзя отменить")
        req.status = RequestStatus.CANCELLED_BY_CUSTOMER
        # менеджеры объекта напрямую + менеджеры категории объекта
        manager_ids = await self.objects.list_access_manager_ids(req.object_id)
        await self.publisher.publish_request_cancelled(
            RequestCancelledEvent(
                request_id=req.id,
                object_id=req.object_id,
                manager_ids=manager_ids,
            )
        )
        return req
