"""Mixin связей «сущность ↔ менеджер».

Общая логика add/remove/list для object_managers и category_managers
без дублирования в каждом репозитории. Mixin работает через self.session
наследника (BaseRepository), link_model — link-модель связи.
"""

from typing import TypeVar

from sqlalchemy import delete, select
from sqlalchemy.orm import InstrumentedAttribute

from app.domain.base import Base

LinkT = TypeVar("LinkT", bound=Base)


class _LinkAttr:
    """Дескриптор колонки связи: не конфликтует с InstrumentedAttribute.

    InstrumentedAttribute — сам дескриптор SQLAlchemy: при доступе через
    инстанс репозитория он пытается работать с ORM-состоянием инстанса
    (UnmappedInstanceError/AttributeError). _LinkAttr всегда возвращает
    колонку — доступ безопасен и через класс, и через инстанс.
    """

    def __init__(self, attr: InstrumentedAttribute[int]) -> None:
        self.attr = attr

    def __get__(self, instance, owner) -> InstrumentedAttribute[int]:
        return self.attr


def link_entity(attr: InstrumentedAttribute[int]) -> _LinkAttr:
    """Маркер колонки связи: link_entity(ObjectManager.object_id)."""
    return _LinkAttr(attr)


class ManagerLinkMixin:
    """CRUD связей «сущность ↔ менеджер».

    Наследник задаёт link_model (ObjectManager / CategoryManager) и
    link_entity_attr = link_entity(ObjectManager.object_id).
    """

    link_model: type[LinkT]
    link_entity_attr: InstrumentedAttribute[int]  # фактически _LinkAttr

    async def add_manager(self, entity_id: int, user_id: int) -> LinkT:
        """Назначить менеджера на сущность."""
        link = self._new_link(entity_id, user_id)
        self.session.add(link)  # type: ignore[attr-defined]
        return link

    def _new_link(self, entity_id: int, user_id: int) -> LinkT:
        """Создать связь с правильным именем колонки (object_id/category_id)."""
        entity_col = self._entity_column_name()
        return self.link_model(**{entity_col: entity_id, "user_id": user_id})  # type: ignore[call-arg]

    def _entity_column_name(self) -> str:
        """Имя колонки сущности в link-модели (из InstrumentedAttribute)."""
        return self.link_entity_attr.key

    async def remove_manager(self, entity_id: int, user_id: int) -> None:
        """Снять менеджера с сущности."""
        link = (
            await self.session.scalars(  # type: ignore[attr-defined]
                select(self.link_model).where(
                    self.link_entity_attr == entity_id,
                    self.link_model.user_id == user_id,
                )
            )
        ).first()
        if link is not None:
            await self.session.delete(link)  # type: ignore[attr-defined]

    async def remove_managers(self, entity_id: int, user_ids: set[int]) -> None:
        """Снять нескольких менеджеров одним DELETE (вместо SELECT+DELETE на каждого)."""
        if not user_ids:
            return
        await self.session.execute(  # type: ignore[attr-defined]
            delete(self.link_model).where(
                self.link_entity_attr == entity_id,
                self.link_model.user_id.in_(user_ids),
            )
        )

    async def list_manager_ids(self, entity_id: int) -> list[int]:
        """Id менеджеров, назначенных на сущность."""
        links = await self.session.scalars(  # type: ignore[attr-defined]
            select(self.link_model.user_id).where(
                self.link_entity_attr == entity_id
            )
        )
        return list(links)
