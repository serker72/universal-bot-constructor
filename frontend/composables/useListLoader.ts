// Загрузка страницы списка: отмена устаревших запросов (гонка ответов
// фильтров) и возврат на предыдущую страницу, если текущая опустела
// (например, после удаления последней записи на последней странице).
import type { Page } from './useApi'

export function useListLoader<T>(
  fetchPage: (offset: number, signal: AbortSignal) => Promise<Page<T>>,
  limit: number,
) {
  const items = ref<T[]>([]) as Ref<T[]>
  const total = ref(0)
  const offset = ref(0)
  let controller: AbortController | null = null

  async function load(): Promise<void> {
    controller?.abort()
    const current = new AbortController()
    controller = current
    try {
      let p = await fetchPage(offset.value, current.signal)
      // страница за пределами списка — последняя непустая
      if (!p.items.length && p.total > 0 && offset.value >= p.total) {
        offset.value = Math.max(0, Math.floor((p.total - 1) / limit) * limit)
        p = await fetchPage(offset.value, current.signal)
      }
      if (current.signal.aborted) return
      items.value = p.items
      total.value = p.total
    } catch (err) {
      if (isAbortError(err) || current.signal.aborted) return
      throw err
    }
  }

  /** Смена страницы/фильтра: ошибки показываются пользователю */
  function changeOffset(v: number, scope = '[list]'): void {
    offset.value = v
    load().catch((err) => showLoadError(err, scope))
  }

  return { items, total, offset, load, changeOffset }
}
