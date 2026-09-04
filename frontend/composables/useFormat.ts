// Форматирование дат: UTC в БД → Europe/Moscow в интерфейсе

const fmt = new Intl.DateTimeFormat('ru-RU', {
  timeZone: 'Europe/Moscow',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

const fmtDate = new Intl.DateTimeFormat('ru-RU', {
  timeZone: 'Europe/Moscow',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return fmt.format(new Date(iso))
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return fmtDate.format(new Date(iso))
}

/** ISO-дата (UTC) из значения input[type=datetime-local] (Europe/Moscow) */
export function moscowToUtc(value: string): string | null {
  if (!value) return null
  // трактуем введённое время как московское (UTC+3)
  const dt = new Date(`${value}:00+03:00`)
  return Number.isNaN(dt.getTime()) ? null : dt.toISOString()
}
