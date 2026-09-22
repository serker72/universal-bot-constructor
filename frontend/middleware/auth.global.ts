// Глобальный middleware: доступ к страницам по роли
// (роль сверяется с сервером через /auth/me — не доверяем localStorage)

const ADMIN_ONLY = ['/categories', '/objects', '/fields', '/users', '/visitors', '/devices', '/sessions', '/settings']

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth()
  if (import.meta.server) return

  if (to.path === '/login') {
    if (auth.isAuthenticated.value) return navigateTo('/dashboard')
    return
  }
  if (!auth.isAuthenticated.value) return navigateTo('/login')
  // сверяем роль с сервером (админ мог изменить её) — не блокируя навигацию
  auth.fetchMe()
  if (ADMIN_ONLY.some((p) => to.path.startsWith(p)) && !auth.isAdmin.value) {
    return navigateTo('/dashboard')
  }
})
