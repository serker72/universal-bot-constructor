// device_id для входа (thumbmarkjs), кэшируется в localStorage.
// Backend требует device_id длиной 8..255 символов, поэтому fingerprint
// хешируется в hex длиной 64 символа — стабильно и гарантированной длины.
// crypto.subtle доступен только в secure context (HTTPS/localhost),
// поэтому предусмотрен чистый JS-фолбэк (FNV-1a) для обычного HTTP.
let cached: string | null = null

/** FNV-1a 32-bit, hex; salt меняет результат каждого прохода */
function fnv1a(value: string, salt: number): string {
  let hash = 0x811c9dc5 ^ salt
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

/** Стабильный hex длиной 64 без crypto.subtle */
function fallbackHash(value: string): string {
  let out = ''
  for (let round = 0; round < 8; round++) {
    out += fnv1a(value, round * 0x9e3779b9)
  }
  return out
}

async function toDeviceHash(value: string): Promise<string> {
  try {
    if (crypto?.subtle) {
      const data = new TextEncoder().encode(value)
      const digest = await crypto.subtle.digest('SHA-256', data)
      return Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('')
    }
  } catch {
    // нет secure context — используем фолбэк
  }
  return fallbackHash(value)
}

/** Случайный id без crypto.randomUUID (недоступен вне secure context) */
function randomId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
}

export async function getDeviceId(): Promise<string> {
  if (cached) return cached
  const stored = localStorage.getItem('ubc_device_id')
  // 64 — длина хеша; короткое значение из старой версии игнорируем
  if (stored && stored.length === 64) {
    cached = stored
    return stored
  }

  let fingerprint = ''
  try {
    const mod = (await import('thumbmarkjs')) as { getFingerprint?: () => Promise<string> }
    if (typeof mod.getFingerprint === 'function') {
      fingerprint = await mod.getFingerprint()
    }
  } catch {
    // fingerprint недоступен — случайный стабильный id
  }

  cached = await toDeviceHash(fingerprint || randomId())
  localStorage.setItem('ubc_device_id', cached)
  return cached
}
