"""Роутер пользователей (только admin)."""

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.api.schemas.common import Page
from app.api.schemas.user import UserIn, UserOut, UserUpdateIn
from app.domain.models import User, UserRole
from app.repository.user import UserRepository
from app.services.auth import AuthService
from app.services.password import hash_password

router = APIRouter(prefix="/users", route_class=DishkaRoute, tags=["users"])


@router.get("", response_model=Page[UserOut])
async def list_users(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
    limit: int = 50,
    offset: int = 0,
) -> Page[UserOut]:
    """Список пользователей."""
    items = await repo.find(limit=limit, offset=offset)
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
        password_hash=hash_password(data.password),
        role=data.role,
        telegram_id=data.telegram_id,
        is_active=data.is_active,
    )
    await repo.add(user)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
) -> UserOut:
    """Получить пользователя."""
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdateIn,
    admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
) -> UserOut:
    """Редактировать пользователя (пароль, роль, telegram_id, активность)."""
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    if data.role is not None:
        # нельзя понизить роль последнего активного admin
        if user.role == UserRole.ADMIN and data.role != UserRole.ADMIN:
            active_admins = await repo.count(
                User.role == UserRole.ADMIN, User.is_active.is_(True)
            )
            if active_admins <= 1:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "Cannot demote the last admin"
                )
        user.role = data.role
    if data.telegram_id is not None:
        user.telegram_id = data.telegram_id
    if data.is_active is not None:
        if user.id == admin.user.id and not data.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot deactivate yourself"
            )
        user.is_active = data.is_active
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    admin: FromDishka[AdminUser],
    repo: FromDishka[UserRepository],
    auth: FromDishka[AuthService],
) -> None:
    """Удалить пользователя (сессии и устройства — CASCADE, токены отзываются)."""
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Cannot delete yourself"
        )
    await auth.revoke_all_for_user(user_id)
    await repo.delete(user)
