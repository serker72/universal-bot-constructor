<template>
  <div>
    <div class="mb-6">
      <h1 class="page-title">Дашборд</h1>
      <p class="page-subtitle mt-1">
        Добро пожаловать, {{ auth.user.value?.username }}
      </p>
    </div>

    <div v-if="auth.isAdmin.value" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <NuxtLink
        v-for="card in cards"
        :key="card.to"
        :to="card.to"
        class="group relative overflow-hidden rounded-2xl border border-gray-100 bg-white p-5 shadow-card transition hover:-translate-y-0.5 hover:shadow-card-hover"
      >
        <div class="flex items-start justify-between">
          <div>
            <div class="text-sm font-medium text-gray-500">{{ card.label }}</div>
            <div class="mt-2 text-3xl font-semibold tracking-tight text-gray-900">
              {{ card.count ?? '—' }}
            </div>
          </div>
          <div
            class="flex h-11 w-11 items-center justify-center rounded-xl shadow-sm"
            :class="card.tint"
          >
            <AppIcon :name="card.icon" class="text-white" />
          </div>
        </div>
        <div class="mt-4 flex items-center gap-1 text-xs font-medium text-primary-600 opacity-0 transition group-hover:opacity-100">
          Перейти
          <AppIcon name="forward" size="sm" />
        </div>
      </NuxtLink>
    </div>

    <div v-else class="card p-8 text-center">
      <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-50">
        <AppIcon name="clipboard" class="h-7 w-7 text-primary-600" />
      </div>
      <h2 class="text-lg font-semibold text-gray-900">Вы вошли как менеджер</h2>
      <p class="mx-auto mt-1 max-w-sm text-sm text-gray-500">
        Вам доступны заявки по вашим объектам: подтверждение, отклонение и выполнение.
      </p>
      <NuxtLink to="/requests" class="btn-primary mt-6">
        <AppIcon name="clipboard" size="sm" />
        Перейти к заявкам
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
const auth = useAuth()
const { page } = useApi()

const counts = ref({
  categories: null as number | null,
  objects: null as number | null,
  requests: null as number | null,
})

onMounted(async () => {
  if (!auth.isAdmin.value) return
  const load = async (url: string, key: 'categories' | 'objects' | 'requests') => {
    try {
      const p = await page<Record<string, unknown>>(url, { limit: 1 })
      counts.value[key] = p.total
    } catch {
      /* дашборд не критичен */
    }
  }
  await Promise.all([
    load('/categories', 'categories'),
    load('/objects', 'objects'),
    load('/requests', 'requests'),
  ])
})

const cards = computed(() => [
  { to: '/categories', label: 'Категории', icon: 'folder', tint: 'bg-gradient-to-br from-sky-400 to-sky-600', count: counts.value.categories },
  { to: '/objects', label: 'Объекты', icon: 'cube', tint: 'bg-gradient-to-br from-violet-400 to-violet-600', count: counts.value.objects },
  { to: '/requests', label: 'Заявки', icon: 'clipboard', tint: 'bg-gradient-to-br from-amber-400 to-amber-600', count: counts.value.requests },
  { to: '/settings', label: 'Настройки', icon: 'cog', tint: 'bg-gradient-to-br from-slate-400 to-slate-600', count: null },
])
</script>
