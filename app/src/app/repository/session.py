"""Репозиторий сессий (refresh-токены)."""

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import update

from app.domain.models import Session
from app.repository.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    model = Session

    async def get_by_jti(self, jti: str) -> Session | None:
        """Сессия по jti refresh-токена."""
        return await self.find_one(Session.refresh_token_jti == jti)

    async def list_by_user(
        self, user_id: int, *, only_active: bool = False
    ) -> Sequence[Session]:
        """Сессии пользователя (опционально только активные)."""
        conditions = [Session.user_id == user_id]
        if only_active:
            conditions.append(Session.is_active.is_(True))
        return await self.find(*conditions, order_by=Session.created_at.desc())

    async def revoke(self, session: Session) -> Session:
        """Отозвать одну сессию."""
        session.is_active = False
        session.revoked_at = datetime.now(timezone.utc)
        return session

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Отозвать все активные сессии пользователя. Возвращает количество."""
        result = await self.session.execute(
            update(Session)
            .where(
                Session.user_id == user_id,
                Session.is_active.is_(True),
            )
            .values(is_active=False, revoked_at=datetime.now(timezone.utc))
        )
        return result.rowcount
