"""Интеграционные тесты AuthService (реальные БД + redis)."""

import pytest
from redis.asyncio import Redis
from starlette.responses import Response

from app.config.settings import Settings
from app.domain.models import User, UserRole
from app.repository.device import DeviceRepository
from app.repository.session import SessionRepository
from app.repository.user import UserRepository
from app.services.auth import ACCESS_COOKIE, REFRESH_COOKIE, AuthError, AuthService
from app.services.security import TokenBlacklist
from app.services.tokens import TokenService


@pytest.fixture
async def service(settings: Settings, db, redis_client: Redis) -> AuthService:
    return AuthService(
        settings=settings,
        session=db,
        users=UserRepository(db),
        devices=DeviceRepository(db),
        sessions=SessionRepository(db),
        tokens=TokenService(settings),
        blacklist=TokenBlacklist(redis_client),
    )


@pytest.fixture
async def redis_client(settings: Settings) -> Redis:
    return Redis.from_url(settings.redis.url)


AUTH_DATA = {"username": "auth-user", "password": "password-123"}


@pytest.fixture
def auth_data() -> dict:
    """Данные пользователя для тестов AuthService."""
    return dict(AUTH_DATA)


@pytest.fixture
async def user(db, auth_data) -> User:
    from app.services.password import hash_password

    user = User(
        username=auth_data["username"],
        password_hash=hash_password(auth_data["password"]),
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    return user


def make_response() -> Response:
    return Response()


def get_cookie(response: Response, name: str) -> str:
    """Значение cookie из set-cookie заголовков starlette Response."""
    from http.cookies import SimpleCookie

    for header in response.headers.getlist("set-cookie"):
        jar = SimpleCookie()
        jar.load(header)
        if name in jar:
            return jar[name].value
    raise AssertionError(f"cookie {name!r} is not set")


async def test_login_success(service: AuthService, user: User, db, auth_data, device_id):
    response = make_response()
    result = await service.login(
        username=auth_data["username"],
        password=auth_data["password"],
        device_id=device_id,
        user_agent="pytest",
        response=response,
    )
    await db.commit()

    assert result.id == user.id

    # cookies установлены
    set_cookies = ",".join(response.headers.getlist("set-cookie"))
    assert f"{ACCESS_COOKIE}=" in set_cookies
    assert f"{REFRESH_COOKIE}=" in set_cookies
    assert "httponly" in set_cookies.lower()

    # устройство зарегистрировано
    devices = await DeviceRepository(db).list_by_user(user.id)
    assert len(devices) == 1
    assert devices[0].device_id == device_id

    # активная сессия с jti из refresh-токена
    sessions = await SessionRepository(db).list_by_user(user.id, only_active=True)
    assert len(sessions) == 1


async def test_login_existing_device_updated(service: AuthService, user: User, db, auth_data, device_id):
    response1 = make_response()
    await service.login(
        username=auth_data["username"],
        password=auth_data["password"],
        device_id=device_id,
        user_agent="first-agent",
        response=response1,
    )
    await db.commit()

    response2 = make_response()
    await service.login(
        username=auth_data["username"],
        password=auth_data["password"],
        device_id=device_id,
        user_agent="second-agent",
        response=response2,
    )
    await db.commit()

    devices = await DeviceRepository(db).list_by_user(user.id)
    assert len(devices) == 1
    assert devices[0].user_agent == "second-agent"


async def test_login_wrong_password(service: AuthService, user: User, auth_data, device_id):
    with pytest.raises(AuthError):
        await service.login(
            username=auth_data["username"],
            password="wrong-password",
            device_id=device_id,
            user_agent=None,
            response=make_response(),
        )


async def test_login_unknown_user(service: AuthService, auth_data, device_id):
    with pytest.raises(AuthError):
        await service.login(
            username="ghost",
            password=auth_data["password"],
            device_id=device_id,
            user_agent=None,
            response=make_response(),
        )


async def test_login_inactive_user(service: AuthService, user: User, db, auth_data, device_id):
    user.is_active = False
    await db.commit()

    with pytest.raises(AuthError):
        await service.login(
            username=auth_data["username"],
            password=auth_data["password"],
            device_id=device_id,
            user_agent=None,
            response=make_response(),
        )


async def test_refresh_rotates_jti(service: AuthService, user: User, db, auth_data, device_id):
    login_response = make_response()
    await service.login(
        username=auth_data["username"],
        password=auth_data["password"],
        device_id=device_id,
        user_agent=None,
        response=login_response,
    )
    await db.commit()

    old_refresh = get_cookie(login_response, REFRESH_COOKIE)
    old_payload = service.tokens.decode_refresh(old_refresh)

    refresh_response = make_response()
    await service.refresh(old_refresh, refresh_response)
    await db.commit()

    # новый refresh выдан и отличается
    new_refresh = get_cookie(refresh_response, REFRESH_COOKIE)
    assert new_refresh != old_refresh
    new_payload = service.tokens.decode_refresh(new_refresh)

    # сессия переведена на новый jti (ротация обновляет ту же строку)
    session = await SessionRepository(db).get_by_jti(new_payload["jti"])
    assert session is not None
    assert session.is_active is True
    # старого jti в БД больше нет
    assert await SessionRepository(db).get_by_jti(old_payload["jti"]) is None

    # старый refresh в blacklist redis
    assert await service.blacklist.is_blacklisted(old_payload["jti"]) is True
    assert await service.blacklist.is_blacklisted(new_payload["jti"]) is False


async def test_refresh_missing_token(service: AuthService, auth_data, device_id):
    with pytest.raises(AuthError):
        await service.refresh(None, make_response())


async def test_refresh_revoked_session(service: AuthService, user: User, db, auth_data, device_id):
    login_response = make_response()
    await service.login(
        username=auth_data["username"],
        password=auth_data["password"],
        device_id=device_id,
        user_agent=None,
        response=login_response,
    )
    await db.commit()

    refresh_token = get_cookie(login_response, REFRESH_COOKIE)
    jti = service.tokens.decode_refresh(refresh_token)["jti"]

    session = await SessionRepository(db).get_by_jti(jti)
    assert session is not None
    await service.sessions.revoke(session)
    await db.commit()

    with pytest.raises(AuthError, match="revoked"):
        await service.refresh(refresh_token, make_response())


async def test_logout_blacklists_and_revokes(
    service: AuthService, user: User, db, redis_client: Redis, auth_data, device_id
):
    login_response = make_response()
    await service.login(
        username=auth_data["username"],
        password=auth_data["password"],
        device_id=device_id,
        user_agent=None,
        response=login_response,
    )
    await db.commit()

    access = get_cookie(login_response, ACCESS_COOKIE)
    refresh = get_cookie(login_response, REFRESH_COOKIE)
    refresh_jti = service.tokens.decode_refresh(refresh)["jti"]

    logout_response = make_response()
    await service.logout(access, refresh, logout_response)
    await db.commit()

    # оба токена в blacklist
    access_jti = service.tokens.decode_access(access)["jti"]
    assert await redis_client.exists(f"auth:blacklist:{access_jti}")
    assert await redis_client.exists(f"auth:blacklist:{refresh_jti}")

    # сессия отозвана
    session = await SessionRepository(db).get_by_jti(refresh_jti)
    assert session.is_active is False

    # cookies удалены (empty значения)
    set_cookies = ",".join(logout_response.headers.getlist("set-cookie"))
    assert f'{ACCESS_COOKIE}=""' in set_cookies


async def test_revoke_all_for_user(service: AuthService, user: User, db, auth_data, device_id):
    for device_id in ("device-1", "device-2"):
        await service.login(
            username=auth_data["username"],
            password=auth_data["password"],
            device_id=device_id,
            user_agent=None,
            response=make_response(),
        )
    await db.commit()

    count = await service.revoke_all_for_user(user.id)
    await db.commit()
    assert count == 2

    sessions = await SessionRepository(db).list_by_user(user.id)
    assert all(s.is_active is False for s in sessions)
