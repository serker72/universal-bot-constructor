"""Создание (обновление) пользователя админки из командной строки.

Идемпотентно: если username уже существует — обновляются хеш пароля,
роль и is_active=True (с предупреждением); повторный запуск безопасен.

Запуск:
    # в контейнере (образ ubc-app, переменные из .env)
    docker compose run --rm backend python -m app.scripts.create_admin --username admin
    # локально (из каталога app/)
    PYTHONPATH=src POSTGRES_HOST=127.0.0.1 ../.venv/bin/python -m app.scripts.create_admin \
        --username admin

Коды выхода: 0 — успех; 1 — неверный ввод (политика пароля, пароли
не совпадают, пустой username); 2 — ошибка подключения/работы с БД.
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable, Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.db.engine import create_engine, create_session_factory
from app.domain.models.user import User, UserRole
from app.log import get_logger, setup_logging
from app.repository.user import UserRepository
from app.services.password import PasswordError, hash_password, validate_password_policy

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_DB_ERROR = 2

logger = get_logger(__name__)


class InputError(ValueError):
    """Неверные входные данные (сообщение выводится без трейсбека)."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Разбор аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.create_admin",
        description="Создать или обновить пользователя админки (admin/manager).",
    )
    parser.add_argument("--username", required=True, help="имя входа")
    parser.add_argument(
        "--password",
        help="пароль (8–72 байта); без флага — запрос с повторным вводом",
    )
    parser.add_argument(
        "--role",
        default=UserRole.ADMIN.value,
        choices=[role.value for role in UserRole],
        help="роль (по умолчанию: %(default)s)",
    )
    return parser.parse_args(argv)


def read_password(
    password: str | None,
    prompt: Callable[[str], str] = getpass.getpass,
) -> str:
    """Пароль из аргумента или интерактивно (с подтверждением) + проверка политики."""
    if password is None:
        password = prompt("Пароль: ")
        if prompt("Повторите пароль: ") != password:
            raise InputError("Пароли не совпадают")
    try:
        validate_password_policy(password)
    except PasswordError as exc:
        raise InputError(str(exc)) from exc
    return password


async def upsert_user(
    session: AsyncSession,
    username: str,
    password_hash: str,
    role: UserRole,
) -> tuple[User, bool]:
    """Создать пользователя или обновить существующего. Возвращает (user, created)."""
    users = UserRepository(session)
    user = await users.get_by_username(username)
    if user is None:
        user = await users.add(
            User(
                username=username,
                password_hash=password_hash,
                role=role,
                is_active=True,
            )
        )
        return user, True

    user.password_hash = password_hash
    user.role = role
    user.is_active = True
    await session.flush()
    return user, False


async def run(settings: Settings, username: str, password: str, role: UserRole) -> None:
    """Подключиться к БД (без DI), выполнить upsert и закрыть движок."""
    engine = create_engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session, session.begin():
            user, created = await upsert_user(
                session, username, hash_password(password), role
            )
        if created:
            logger.info("user_created", username=user.username, role=role.value, id=user.id)
        else:
            logger.warning(
                "user_updated",
                username=user.username,
                role=role.value,
                id=user.id,
                detail="пользователь уже существовал: обновлены пароль, роль, is_active",
            )
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа CLI; возвращает код выхода."""
    args = parse_args(argv)
    settings = Settings()
    setup_logging(debug=settings.project.environment != "prod")

    try:
        username = args.username.strip()
        if not username:
            raise InputError("Имя пользователя не может быть пустым")
        password = read_password(args.password)
    except InputError as exc:
        logger.error("invalid_input", detail=str(exc))
        return EXIT_INPUT_ERROR

    try:
        asyncio.run(run(settings, username, password, UserRole(args.role)))
    except (SQLAlchemyError, OSError) as exc:
        logger.error("db_error", detail=str(exc))
        return EXIT_DB_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
