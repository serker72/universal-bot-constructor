"""Тесты CLI создания администратора (app.scripts.create_admin) без БД.

Сессия — фейковая; репозиторий UserRepository подменяется заглушкой.
"""

import pytest

from app.domain.models.user import User, UserRole
from app.scripts import create_admin
from app.scripts.create_admin import (
    EXIT_INPUT_ERROR,
    InputError,
    parse_args,
    read_password,
    upsert_user,
)


class FakeSession:
    """Заглушка AsyncSession: считает flush и execute (отзыв сессий)."""

    def __init__(self) -> None:
        self.flushed = 0
        self.executed = 0

    async def flush(self) -> None:
        self.flushed += 1

    async def execute(self, stmt):  # noqa: ANN001
        self.executed += 1

        class _Result:
            rowcount = 0

        return _Result()


class FakeUserRepository:
    """Заглушка UserRepository: пользователи в dict по username."""

    storage: dict[str, User] = {}

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def get_by_username(self, username: str) -> User | None:
        return self.storage.get(username)

    async def add(self, obj: User) -> User:
        obj.id = len(self.storage) + 1
        self.storage[obj.username] = obj
        await self.session.flush()
        return obj


@pytest.fixture
def fake_repo(monkeypatch):
    FakeUserRepository.storage = {}
    monkeypatch.setattr(create_admin, "UserRepository", FakeUserRepository)
    return FakeUserRepository


# --- parse_args ---


def test_parse_args_defaults():
    args = parse_args(["--username", "admin"])
    assert args.username == "admin"
    assert args.password is None
    assert args.role == "admin"


def test_parse_args_manager_role_and_password():
    args = parse_args(["--username", "m1", "--password", "secret-pass-123", "--role", "manager"])
    assert args.role == "manager"
    assert args.password == "secret-pass-123"


def test_parse_args_username_required():
    with pytest.raises(SystemExit):
        parse_args([])


def test_parse_args_invalid_role():
    with pytest.raises(SystemExit):
        parse_args(["--username", "admin", "--role", "root"])


# --- read_password ---


def test_read_password_from_argument():
    assert read_password("secret-pass-123") == "secret-pass-123"


def test_read_password_interactive_confirmed():
    answers = iter(["secret-pass-123", "secret-pass-123"])
    assert read_password(None, prompt=lambda _: next(answers)) == "secret-pass-123"


def test_read_password_interactive_mismatch():
    answers = iter(["secret-pass-123", "other-pass-1234"])
    with pytest.raises(InputError, match="не совпадают"):
        read_password(None, prompt=lambda _: next(answers))


@pytest.mark.parametrize("password", ["short", "x" * 73, "Password123"])
def test_read_password_policy_violation(password):
    with pytest.raises(InputError):
        read_password(password)


# --- upsert_user ---


async def test_upsert_creates_user(fake_repo):
    session = FakeSession()
    user, created = await upsert_user(session, "admin", "hash-1", UserRole.ADMIN)
    assert created is True
    assert user.username == "admin"
    assert user.password_hash == "hash-1"
    assert user.role is UserRole.ADMIN
    assert user.is_active is True


async def test_upsert_updates_existing_user(fake_repo):
    existing = User(
        username="m1", password_hash="old", role=UserRole.MANAGER, is_active=False
    )
    existing.id = 7
    fake_repo.storage["m1"] = existing
    session = FakeSession()

    user, created = await upsert_user(session, "m1", "new-hash", UserRole.ADMIN)

    assert created is False
    assert user is existing
    assert user.id == 7
    assert user.password_hash == "new-hash"
    assert user.role is UserRole.ADMIN
    assert user.is_active is True
    assert session.flushed == 1
    # смена пароля отзывает сессии пользователя (UPDATE sessions)
    assert session.executed == 1


# --- main: ошибки ввода без обращения к БД ---


def test_main_invalid_password_exit_code(monkeypatch):
    called = False

    async def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(create_admin, "run", fake_run)
    code = create_admin.main(["--username", "admin", "--password", "short"])
    assert code == EXIT_INPUT_ERROR
    assert called is False


def test_main_blank_username_exit_code(monkeypatch):
    monkeypatch.setattr(create_admin, "run", lambda *a, **k: None)
    code = create_admin.main(["--username", "   ", "--password", "secret-pass-123"])
    assert code == EXIT_INPUT_ERROR
