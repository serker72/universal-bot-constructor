// Глобальный middleware: доступ к страницам по роли.
// Роль сверяется с сервером через /auth/me (не доверяем localStorage):
// один раз за сессию SPA (и после входа), до проверки ADMIN_ONLY.

// /categories и /objects менеджеру доступны на чтение (backend фильтрует
// по доступным объектам/категориям), запись — по-прежнему только admin
const ADMIN_ONLY = ['/fields', '/users', '/visitors', '/devices', '/sessions', '/settings']

export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) return
  // composables — синхронно, до первого await (контекст Nuxt)
  const auth = useAuth()

  if (to.path === '/login') {
    if (auth.isAuthenticated.value) return navigateTo('/dashboard')
    return
  }
  if (!auth.isAuthenticated.value) return navigateTo('/login')
  // роль с сервера — до проверки доступа (кешируется до следующего входа)
  await auth.ensureVerified()
  if (!auth.isAuthenticated.value) return navigateTo('/login')
  if (ADMIN_ONLY.some((p) => to.path.startsWith(p)) && !auth.isAdmin.value) {
    return navigateTo('/dashboard')
  }
})
