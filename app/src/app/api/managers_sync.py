"""Общая логика роутеров: синхронизация менеджеров сущности.

Используется роутерами категорий и объектов (PUT /{id}/managers):
проверка существования пользователей (одним batch-запросом),
diff множеств и добавление/удаление связей.
"""

from fastapi import HTTPException, status

from app.domain.models import UserRole
from app.repository.manager_link import ManagerLinkMixin
from app.repository.user import UserRepository


async def sync_managers(
    repo: ManagerLinkMixin,
    entity_id: int,
    user_ids: list[int],
    users: UserRepository,
    *,
    require_manager_role: bool = False,
) -> list[int]:
    """Заменить список менеджеров сущности (категория/объект).

    Возвращает отсортированный итоговый список id.
    require_manager_role=True — все указанные должны иметь роль manager
    (объекты и категории: admin уведомления получал бы, а обработать
    заявку не может).
    """
    target = set(user_ids)
    # один batch-запрос вместо N+1 (users.get в цикле)
    found = await users.list_by_ids(list(target))
    found_ids = {u.id for u in found}
    missing = target - found_ids
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"User(s) not found: {', '.join(str(i) for i in sorted(missing))}",
        )
    if require_manager_role:
        not_managers = {u.id for u in found if u.role != UserRole.MANAGER}
        if not_managers:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"User(s) are not managers: "
                f"{', '.join(str(i) for i in sorted(not_managers))}",
            )
    current = set(await repo.list_manager_ids(entity_id))
    # снятие одним DELETE ... WHERE user_id IN (...)
    await repo.remove_managers(entity_id, current - target)
    for user_id in target - current:
        await repo.add_manager(entity_id, user_id)
    return sorted(target)
