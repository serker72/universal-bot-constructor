// API-клиент: httpOnly cookies (credentials), авто-refresh при 401
export const PAGE_SIZE = 20
// Максимальный limit списков backend (Query le=100)
export const MAX_PAGE_LIMIT = 100

interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

// Single-flight refresh: параллельные 401 ждут один общий запрос /auth/refresh
// (иначе каждый шлёт refresh со старой cookie, первый ротирует jti, остальные
// получают 401 и выбрасывают пользователя на /login)
let refreshInFlight: Promise<boolean> | null = null

/** Текст ошибки API для пользователя (detail из ответа backend или fallback) */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { data?: { detail?: unknown } })?.data?.detail
  if (typeof detail === 'string' && detail) return `${fallback}: ${detail}`
  if (Array.isArray(detail) && detail.length) {
    const msg = (detail[0] as { msg?: string })?.msg
    if (msg) return `${fallback}: ${msg}`
  }
  return fallback
}

/** Общий обработчик ошибки загрузки списка: вывод пользователю (без unhandled rejection) */
export function showLoadError(err: unknown, scope: string): void {
  // 401 — api() уже перенаправил на /login
  if ((err as { status?: number })?.status === 401) return
  console.warn(`${scope} load failed`, err)
  alert(apiErrorMessage(err, 'Не удалось загрузить данные'))
}

/** Признак отмены запроса (AbortController) — не ошибка для пользователя */
export function isAbortError(err: unknown): boolean {
  const e = err as { name?: string; cause?: { name?: string } }
  return e?.name === 'AbortError' || e?.cause?.name === 'AbortError'
}

export function useApi() {
  const config = useRuntimeConfig()
  const baseURL = config.public.backendUrl
  // контекст Nuxt захватываем синхронно: после await composables вызывать нельзя
  const nuxtApp = useNuxtApp()

  function refresh(): Promise<boolean> {
    if (!refreshInFlight) {
      refreshInFlight = $fetch('/auth/refresh', { baseURL, method: 'POST', credentials: 'include' })
        .then(() => true)
        .catch(() => false)
        .finally(() => {
          refreshInFlight = null
        })
    }
    return refreshInFlight
  }

  /** Запрос к API с одним авто-refresh при 401 и повтором исходного запроса */
  async function api<T>(url: string, options: Record<string, unknown> = {}): Promise<T> {
    const doFetch = () =>
      $fetch<T>(url, { baseURL, credentials: 'include', ...options })

    try {
      return await doFetch()
    } catch (err) {
      const status = (err as { status?: number }).status
      // refresh/login сами по себе не повторяем (иначе рекурсия и ложные повторы)
      if (status !== 401 || url === '/auth/refresh' || url === '/auth/login') throw err
      if (await refresh()) return await doFetch()
      await nuxtApp.runWithContext(async () => {
        useAuth().reset()
        await navigateTo('/login')
      })
      throw err
    }
  }

  /** GET-страница списка (signal — отмена устаревшего запроса) */
  function page<T>(
    url: string,
    params: Record<string, unknown> = {},
    signal?: AbortSignal,
  ): Promise<Page<T>> {
    return api<Page<T>>(url, { params, signal })
  }

  /** Все элементы справочника: постранично по MAX_PAGE_LIMIT (без молчаливой обрезки) */
  async function pageAll<T>(url: string, params: Record<string, unknown> = {}): Promise<T[]> {
    const items: T[] = []
    let offset = 0
    for (;;) {
      const p = await page<T>(url, { ...params, limit: MAX_PAGE_LIMIT, offset })
      items.push(...p.items)
      offset += p.items.length
      if (!p.items.length || offset >= p.total) return items
    }
  }

  return { api, page, pageAll, baseURL, refresh }
}

export type { Page }
