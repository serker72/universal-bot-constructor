"""Сервис бота: регистрация посетителей, меню, заявки, отмена."""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Category, Object, Request, RequestStatus, Visitor
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository
from app.repository.request import RequestRepository
from app.repository.visitor import VisitorRepository
from app.services.app_settings import AppSettingsService
from app.services.events import EventPublisher, RequestCancelledEvent, RequestCreatedEvent, VisitorRegisteredEvent

PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


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
        app_settings: AppSettingsService,
        publisher: EventPublisher,
    ) -> None:
        self.session = session
        self.visitors = visitors
        self.categories = categories
        self.objects = objects
        self.requests = requests
        self.app_settings = app_settings
        self.publisher = publisher

    # -- регистрация --------------------------------------------------------

    async def get_visitor(self, telegram_id: int) -> Visitor | None:
        """Посетитель по telegram_id."""
        return await self.visitors.get_by_telegram_id(telegram_id)

    async def register_visitor(self, telegram_id: int, full_name: str) -> Visitor:
        """Завершить регистрацию: согласие уже дано (вызывается после consent)."""
        visitor = await self.visitors.get_by_telegram_id(telegram_id)
        now = datetime.now(timezone.utc)
        if visitor is None:
            visitor = Visitor(
                telegram_id=telegram_id,
                full_name=full_name,
                consent_given=True,
                consent_at=now,
            )
            await self.visitors.add(visitor)
        else:
            visitor.full_name = full_name
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

    async def create_request(
        self, visitor: Visitor, object_id: int, phone: str, comment: str | None
    ) -> Request:
        """Создать заявку (статус «новая») и уведомить менеджеров объекта."""
        obj = await self.get_object(object_id)
        if obj is None:
            raise BotServiceError("Объект не найден")
        req = Request(
            visitor_id=visitor.id,
            object_id=object_id,
            phone=phone,
            comment=comment,
            status=RequestStatus.NEW,
        )
        await self.requests.add(req)
        manager_ids = await self.objects.list_manager_ids(object_id)
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
        manager_ids = await self.objects.list_manager_ids(req.object_id)
        await self.publisher.publish_request_cancelled(
            RequestCancelledEvent(
                request_id=req.id,
                object_id=req.object_id,
                manager_ids=manager_ids,
            )
        )
        return req
