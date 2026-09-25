// Composable списка менеджеров (роль manager, активные) — общий для страниц
// категорий и объектов (модалки «Менеджеры»). Список перечитывается при каждом
// открытии модалки (force), чтобы новые/деактивированные менеджеры не терялись.

interface ManagerUser {
  id: number
  username: string
  role: 'admin' | 'manager'
  is_active: boolean
}

export function useManagers() {
  const managers = useState<ManagerUser[]>('managers-list', () => [])
  const loaded = useState<boolean>('managers-loaded', () => false)

  /** Активные менеджеры (force — перечитать с сервера) */
  async function loadManagers(force = false): Promise<void> {
    if (loaded.value && !force) return
    const { pageAll } = useApi()
    const users = await pageAll<ManagerUser>('/users')
    managers.value = users.filter((u) => u.role === 'manager' && u.is_active)
    loaded.value = true
  }

  return { managers, loadManagers }
}
