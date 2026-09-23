<template>
  <div>
    <div class="mb-6">
      <h1 class="page-title">Дашборд</h1>
      <p class="page-subtitle mt-1">
        Добро пожаловать, {{ auth.user.value?.username }}
      </p>
    </div>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
              <template v-if="card.countNew !== undefined">
                <NuxtLink
                  :to="{ path: '/requests', query: { status: 'new' } }"
                  class="hover:underline"
                  :class="{ 'text-amber-600': card.countNew > 0 }"
                  @click.stop
                >{{ card.countNew ?? '—' }}</NuxtLink>
                <span class="mx-1 text-xl text-gray-400">/</span>
                <span>{{ card.count ?? '—' }}</span>
              </template>
              <template v-else>{{ card.count ?? '—' }}</template>
            </div>
          </div>
          <div
            class="flex h-11 w-11 items-center justify-center rounded-xl shadow-sm"
            :class="card.tint"
          >
            <AppIcon :name="card.icon" class="text-white" />
          </div>
        </div>
        <div class="mt-1 flex items-center gap-1 text-[11px] text-gray-400">
          <template v-if="card.countNew !== undefined">
            новые / все
          </template>
        </div>
        <div class="mt-4 flex items-center gap-1 text-xs font-medium text-primary-600 opacity-0 transition group-hover:opacity-100">
          Перейти
          <AppIcon name="forward" size="sm" />
        </div>
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
  requestsNew: null as number | null,
})

onMounted(async () => {
  // обе роли: backend отдаёт менеджеру только его объекты/категории/заявки
  const load = async (
    url: string,
    key: 'categories' | 'objects' | 'requests' | 'requestsNew',
    params: Record<string, unknown> = {},
  ) => {
    try {
      const p = await page<Record<string, unknown>>(url, { limit: 1, ...params })
      counts.value[key] = p.total
    } catch (err) {
      console.warn('[dashboard] stats load failed', err)
    }
  }
  await Promise.all([
    load('/categories', 'categories'),
    load('/objects', 'objects'),
    load('/requests', 'requests'),
    // новые заявки — отдельным запросом с фильтром по статусу
    load('/requests', 'requestsNew', { status_filter: 'new' }),
  ])
})

// менеджеру «Настройки» недоступны
const cards = computed(() => {
  const all = [
    { to: '/categories', label: 'Категории', icon: 'folder', tint: 'bg-gradient-to-br from-sky-400 to-sky-600', count: counts.value.categories },
    { to: '/objects', label: 'Объекты', icon: 'cube', tint: 'bg-gradient-to-br from-violet-400 to-violet-600', count: counts.value.objects },
    { to: '/requests', label: 'Заявки', icon: 'clipboard', tint: 'bg-gradient-to-br from-amber-400 to-amber-600', count: counts.value.requests, countNew: counts.value.requestsNew },
    { to: '/settings', label: 'Настройки', icon: 'cog', tint: 'bg-gradient-to-br from-slate-400 to-slate-600', count: null },
  ]
  return auth.isAdmin.value ? all : all.filter((c) => c.to !== '/settings')
})
</script>
