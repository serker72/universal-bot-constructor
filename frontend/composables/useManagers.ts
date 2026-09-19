// Composable списка менеджеров (роль manager, активные) — общий для страниц
// категорий и объектов (модалки «Менеджеры»). Загружается один раз и
// переиспользуется между страницами (useState).

interface ManagerUser {
  id: number
  username: string
  role: 'admin' | 'manager'
  is_active: boolean
}

export function useManagers() {
  const managers = useState<ManagerUser[]>('managers-list', () => [])
  const loaded = useState<boolean>('managers-loaded', () => false)

  /** Активные менеджеры (однократная загрузка, повторно не запрашивается) */
  async function loadManagers(force = false): Promise<void> {
    if (loaded.value && !force) return
    try {
      const { page } = useApi()
      const p = await page<ManagerUser>('/users', { limit: 1000 })
      managers.value = p.items.filter((u) => u.role === 'manager' && u.is_active)
      loaded.value = true
    } catch (err) {
      // не критично: модалка покажет «нет менеджеров»
      console.warn('[useManagers] failed to load managers', err)
    }
  }

  return { managers, loadManagers }
}
