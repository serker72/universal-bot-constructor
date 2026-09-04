// API-клиент: httpOnly cookies (credentials), авто-refresh при 401
export const PAGE_SIZE = 20

interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export function useApi() {
  const config = useRuntimeConfig()
  const baseURL = config.public.backendUrl

  async function refresh(): Promise<boolean> {
    try {
      await $fetch('/auth/refresh', { baseURL, method: 'POST', credentials: 'include' })
      return true
    } catch {
      return false
    }
  }

  /** Запрос к API с одним авто-refresh при 401 */
  async function api<T>(url: string, options: Record<string, unknown> = {}): Promise<T> {
    const doFetch = () =>
      $fetch<T>(url, { baseURL, credentials: 'include', ...options })

    try {
      return await doFetch()
    } catch (err) {
      const status = (err as { status?: number }).status
      if (status === 401 && !(await refresh())) {
        const auth = useAuth()
        auth.reset()
        await navigateTo('/login')
      }
      throw err
    }
  }

  /** GET-страница списка */
  function page<T>(url: string, params: Record<string, unknown> = {}): Promise<Page<T>> {
    return api<Page<T>>(url, { params })
  }

  return { api, page, baseURL, refresh }
}

export type { Page }
