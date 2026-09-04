"""Репозиторий пользователей."""

from collections.abc import Sequence

from sqlalchemy import select

from app.domain.models import User, UserRole
from app.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, username: str) -> User | None:
        """Пользователь по имени входа."""
        return await self.find_one(User.username == username)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Пользователь по привязанному telegram_id (для уведомлений)."""
        return await self.find_one(User.telegram_id == telegram_id)

    async def list_telegram_ids_by_role(self, role: UserRole) -> list[int]:
        """Telegram-id активных пользователей роли (для уведомлений)."""
        stmt = select(User.telegram_id).where(
            User.role == role,
            User.is_active.is_(True),
            User.telegram_id.is_not(None),
        )
        return list(await self.session.scalars(stmt))

    async def list_telegram_ids_by_ids(
        self, user_ids: Sequence[int]
    ) -> list[int]:
        """Telegram-id активных пользователей по списку id (для уведомлений)."""
        if not user_ids:
            return []
        stmt = select(User.telegram_id).where(
            User.id.in_(user_ids),
            User.is_active.is_(True),
            User.telegram_id.is_not(None),
        )
        return list(await self.session.scalars(stmt))
