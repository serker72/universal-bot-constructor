// Справочники «id → подпись» для колонок таблиц (категория объекта,
// объект заявки, пользователь сессии/устройства). Nuxt автоимпортирует utils/.

/** Запись справочника, у которой есть подпись (name или username) */
export interface Named {
  id: number
  name?: string
  username?: string
}

/**
 * Подпись записи по id; если запись не загружена/недоступна (чужая запись
 * менеджера, удалённая) — прежний fallback `#{id}`.
 */
export function nameById(items: Named[], id: number): string {
  const item = items.find((i) => i.id === id)
  return item?.name ?? item?.username ?? `#${id}`
}
