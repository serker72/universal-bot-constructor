// Глобальный middleware: доступ к страницам по роли

const ADMIN_ONLY = ['/categories', '/objects', '/users', '/visitors', '/devices', '/sessions', '/settings']

export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuth()
  if (import.meta.server) return

  if (to.path === '/login') {
    if (auth.isAuthenticated.value) return navigateTo('/dashboard')
    return
  }
  if (!auth.isAuthenticated.value) return navigateTo('/login')
  if (ADMIN_ONLY.some((p) => to.path.startsWith(p)) && !auth.isAdmin.value) {
    return navigateTo('/dashboard')
  }
})
