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

  const isAdmin = computed(() => user.value?.role === 'admin')
  const isAuthenticated = computed(() => user.value !== null)

  function persist() {
    if (user.value) localStorage.setItem(STORAGE_KEY, JSON.stringify(user.value))
    else localStorage.removeItem(STORAGE_KEY)
  }

  async function login(username: string, password: string): Promise<void> {
    const { api } = useApi()
    const device_id = await getDeviceId()
    const u = await api<AuthUser>('/auth/login', {
      method: 'POST',
      body: { username, password, device_id },
    })
    user.value = u
    persist()
  }

  /** Сверить сохранённого пользователя с сервером (роль — источник истины) */
  async function fetchMe(): Promise<void> {
    if (!user.value) return
    const { api } = useApi()
    try {
      const u = await api<AuthUser>('/auth/me')
      // роль могла измениться админом — обновляем локальную копию
      if (u.role !== user.value.role || u.username !== user.value.username) {
        user.value = u
        persist()
      }
    } catch {
      // 401 и т.п. — api() сам сделает refresh/redirect
    }
  }

  async function logout(): Promise<void> {
    try {
      const { api } = useApi()
      await api('/auth/logout', { method: 'POST' })
    } catch {
      // даже если logout не удался — локально выходим
    }
    reset()
    await navigateTo('/login')
  }

  function reset() {
    user.value = null
    persist()
  }

  return { user, isAdmin, isAuthenticated, login, logout, reset, fetchMe }
}
