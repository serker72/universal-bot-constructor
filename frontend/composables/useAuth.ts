// Аутентификация: пользователь хранится в useState + localStorage
// (токены — только в httpOnly cookies, JS их не видит)

interface AuthUser {
  id: number
  username: string
  role: 'admin' | 'manager'
}

const STORAGE_KEY = 'ubc_user'

export function useAuth() {
  const user = useState<AuthUser | null>('auth-user', () => {
    if (import.meta.server) return null
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? (JSON.parse(raw) as AuthUser) : null
    } catch {
      return null
    }
  })

  // роль сверена с сервером в текущей сессии SPA (один /auth/me, а не на каждый переход)
  const verified = useState<boolean>('auth-verified', () => false)

  // composables — синхронно при создании (после await контекст Nuxt потерян)
  const nuxtApp = useNuxtApp()
  const { api } = useApi()

  const isAdmin = computed(() => user.value?.role === 'admin')
  const isAuthenticated = computed(() => user.value !== null)

  function persist() {
    if (user.value) localStorage.setItem(STORAGE_KEY, JSON.stringify(user.value))
    else localStorage.removeItem(STORAGE_KEY)
  }

  async function login(username: string, password: string): Promise<void> {
    const device_id = await getDeviceId()
    const u = await api<AuthUser>('/auth/login', {
      method: 'POST',
      body: { username, password, device_id },
    })
    user.value = u
    verified.value = true
    persist()
  }

  /** Сверить сохранённого пользователя с сервером (роль — источник истины) */
  async function fetchMe(): Promise<void> {
    if (!user.value) return
    try {
      const u = await api<AuthUser>('/auth/me')
      // роль могла измениться админом — обновляем локальную копию
      if (u.role !== user.value?.role || u.username !== user.value?.username) {
        user.value = u
        persist()
      }
      verified.value = true
    } catch {
      // 401 — api() сам сделает refresh/redirect и reset()
    }
  }

  /** Одна сверка роли с сервером за сессию SPA (middleware ждёт её до проверки доступа) */
  async function ensureVerified(): Promise<void> {
    if (verified.value || !user.value) return
    await fetchMe()
  }

  async function logout(): Promise<void> {
    try {
      await api('/auth/logout', { method: 'POST' })
    } catch {
      // даже если logout не удался — локально выходим
    }
    reset()
    await nuxtApp.runWithContext(() => navigateTo('/login'))
  }

  function reset() {
    user.value = null
    verified.value = false
    persist()
  }

  return { user, isAdmin, isAuthenticated, login, logout, reset, fetchMe, ensureVerified }
}
