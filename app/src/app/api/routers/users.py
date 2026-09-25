"""Роутер пользователей (только admin)."""

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import FromDishka

from app.api.routing import TransactionalRoute
from app.api.deps import AdminUser, flush_or_400, get_or_404
from app.api.schemas.common import LimitQuery, OffsetQuery, Page
from app.api.schemas.user import UserIn, UserOut, UserUpdateIn
from app.domain.models import User, UserRole
from app.repository.user import UserRepository
from app.services.auth import AuthService
from app.services.password import PasswordError, hash_password_async

router = APIRouter(prefix="/users", route_class=TransactionalRoute, tags=["users"])


async def _hash_or_400(password: str) -> str:
    """Хеш пароля; нарушение политики (длина в байтах и т.п.) — 400, а не 500."""
    try:
        return await hash_password_async(password)
    except PasswordError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("", response_model=Page[UserOut])
async def list_users(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Page[UserOut]:
    """Список пользователей."""
    items = await repo.find(limit=limit, offset=offset, order_by=User.id)
    total = await repo.count()
    return Page(
        items=[UserOut.model_validate(u) for u in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
) -> UserOut:
    """Создать пользователя (admin или manager)."""
    if await repo.get_by_username(data.username):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Username already exists"
        )
    user = User(
        username=data.username,
        password_hash=await _hash_or_400(data.password),
        role=data.role,
        telegram_id=data.telegram_id,
        is_active=data.is_active,
    )
    repo.session.add(user)
    # гонка: username (или telegram_id) занят между проверкой и insert
    await flush_or_400(repo.session, "Username or telegram_id already exists")
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
) -> UserOut:
    """Получить пользователя."""
    user = get_or_404(await repo.get(user_id), "User not found")
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdateIn,
    admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
    auth: FromDishka[AuthService],
) -> UserOut:
    """Редактировать пользователя (пароль, роль, telegram_id, активность).

    PATCH-семантика: отсутствующий ключ — не менять; ``telegram_id: null`` —
    очистить (уведомления в Telegram отключаются).
    """
    user = get_or_404(await repo.get(user_id), "User not found")
    fields = data.model_fields_set
    password_changed = False
    if data.password is not None:
        user.password_hash = await _hash_or_400(data.password)
        password_changed = True
    if data.role is not None:
        # нельзя понизить роль последнего активного admin (понижение
        # неактивного admin на число активных не влияет)
        if (
            user.role == UserRole.ADMIN
            and data.role != UserRole.ADMIN
            and user.is_active
        ):
            active_admins = await repo.count(
                User.role == UserRole.ADMIN, User.is_active.is_(True)
            )
            if active_admins <= 1:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "Cannot demote the last admin"
                )
        user.role = data.role
    if "telegram_id" in fields:
        user.telegram_id = data.telegram_id
    if data.is_active is not None:
        if user.id == admin.user.id and not data.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot deactivate yourself"
            )
        user.is_active = data.is_active
    # telegram_id уникален — конфликт должен дать 400 до ответа, а не на commit
    await flush_or_400(repo.session, "telegram_id already in use")
    if password_changed:
        # украденные токены (refresh и access) перестают работать сразу
        await auth.revoke_all_for_user(user.id)
    # updated_at (server onupdate) истёк после flush — перечитать до
    # сериализации, иначе ленивая загрузка в async даёт MissingGreenlet
    await repo.session.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
    auth: FromDishka[AuthService],
) -> None:
    """Удалить пользователя (сессии и устройства — CASCADE, токены отзываются)."""
    user = get_or_404(await repo.get(user_id), "User not found")
    if user.id == admin.user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Cannot delete yourself"
        )
    await auth.revoke_all_for_user(user_id)
    await repo.delete(user)
