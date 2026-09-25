"""Route-класс API: транзакция запроса завершается ДО отправки ответа.

dishka закрывает REQUEST-scope (и финализатор сессии с commit) уже после
того, как ответ отправлен клиенту: ошибка commit (IntegrityError и т.п.)
превращалась в «200 OK» при фактическом откате изменений. TransactionalRoute
делает commit сразу после эндпоинта — ошибка commit даёт ошибку ответа,
а при исключении в эндпоинте (включая HTTPException) изменения откатываются.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from dishka.integrations.fastapi import DishkaRoute
from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession


class TransactionalRoute(DishkaRoute):
    """DishkaRoute + commit/rollback сессии БД запроса до формирования ответа."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            container = request.state.dishka_container
            try:
                response = await handler(request)
            except Exception:
                session = await container.get(AsyncSession)
                await session.rollback()
                raise
            session = await container.get(AsyncSession)
            await session.commit()
            return response

        return route_handler
