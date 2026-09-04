<template>
  <div class="flex min-h-screen">
    <!-- Сайдбар -->
    <aside class="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col bg-slate-900 shadow-sidebar md:flex">
      <!-- Логотип -->
      <div class="flex items-center gap-2.5 px-5 py-5">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 shadow-lg shadow-primary-500/30">
          <AppIcon name="chat" size="sm" class="text-white" />
        </div>
        <div>
          <div class="text-sm font-semibold text-white">Конструктор меню</div>
          <div class="text-[11px] text-slate-400">Telegram-бот</div>
        </div>
      </div>

      <!-- Навигация -->
      <nav class="flex-1 space-y-1 overflow-y-auto px-3 py-3">
        <NuxtLink
          v-for="item in menu"
          :key="item.to"
          :to="item.to"
          class="sidebar-link"
          :class="{ 'sidebar-link-active': isActive(item.to) }"
        >
          <AppIcon :name="item.icon" size="sm" />
          {{ item.label }}
        </NuxtLink>
      </nav>

      <!-- Пользователь -->
      <div class="border-t border-white/10 p-3">
        <div class="flex items-center gap-3 rounded-lg bg-white/5 px-3 py-2.5">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-500/20 text-xs font-semibold text-primary-200">
            {{ initials }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium text-white">{{ auth.user.value?.username }}</div>
            <div class="text-[11px] text-slate-400">{{ auth.isAdmin.value ? 'Администратор' : 'Менеджер' }}</div>
          </div>
          <button
            class="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white"
            title="Выйти"
            @click="auth.logout()"
          >
            <AppIcon name="logout" size="sm" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Контент -->
    <div class="flex min-w-0 flex-1 flex-col md:pl-60">
      <!-- Топбар (мобильный) -->
      <header class="sticky top-0 z-20 flex items-center justify-between border-b border-gray-100 bg-white/90 px-4 py-3 shadow-sm backdrop-blur md:hidden">
        <div class="flex items-center gap-2">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary-400 to-primary-600">
            <AppIcon name="chat" size="sm" class="text-white" />
          </div>
          <span class="text-sm font-semibold">Конструктор меню</span>
        </div>
        <button class="btn-ghost !px-2.5" title="Выйти" @click="auth.logout()">
          <AppIcon name="logout" size="sm" />
        </button>
      </header>

      <main class="mx-auto w-full max-w-7xl flex-1 p-4 md:p-8">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
const auth = useAuth()
const route = useRoute()

const adminMenu = [
  { to: '/dashboard', label: 'Дашборд', icon: 'dashboard' },
  { to: '/categories', label: 'Категории', icon: 'folder' },
  { to: '/objects', label: 'Объекты', icon: 'cube' },
  { to: '/requests', label: 'Заявки', icon: 'clipboard' },
  { to: '/users', label: 'Пользователи', icon: 'users' },
  { to: '/visitors', label: 'Посетители', icon: 'visitor' },
  { to: '/devices', label: 'Устройства', icon: 'device' },
  { to: '/sessions', label: 'Сессии', icon: 'key' },
  { to: '/settings', label: 'Настройки', icon: 'cog' },
]

const managerMenu = [
  { to: '/dashboard', label: 'Дашборд', icon: 'dashboard' },
  { to: '/requests', label: 'Заявки', icon: 'clipboard' },
]

const menu = computed(() => (auth.isAdmin.value ? adminMenu : managerMenu))
const isActive = (to: string) => route.path.startsWith(to)

const initials = computed(() =>
  (auth.user.value?.username ?? '?').slice(0, 2).toUpperCase(),
)
</script>
