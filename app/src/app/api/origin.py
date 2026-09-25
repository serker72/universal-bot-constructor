"""Проверка Origin для cookie-аутентификации (защита от CSRF в глубину).

SameSite=lax не защищает от same-site-вектора (соседний поддомен) для
POST/PUT/PATCH/DELETE. Мутирующие запросы с заголовком Origin, не входящим
в CORS_ORIGINS, отклоняются 403. Запросы без Origin (curl, server-to-server,
тесты) пропускаются: браузеры передают Origin во всех cross-origin и
same-origin мутирующих fetch/XHR запросах.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class OriginCheckMiddleware:
    """ASGI-middleware: 403 для мутирующих запросов с чужим Origin."""

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed = {o.rstrip("/") for o in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            origin = None
            for name, value in scope["headers"]:
                if name == b"origin":
                    origin = value.decode("latin-1").rstrip("/")
                    break
            if origin is not None and origin not in self.allowed:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"detail":"Origin not allowed"}',
                    }
                )
                return
        await self.app(scope, receive, send)
