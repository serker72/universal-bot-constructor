<template>
  <div>
    <h1 class="page-title mb-4">Устройства</h1>

    <div class="card mb-4 max-w-xs p-4">
      <label class="label" for="d-user">Фильтр по пользователю</label>
      <select id="d-user" v-model="userId" class="input" @change="changeOffset(0)">
        <option value="">Все пользователи</option>
        <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
      </select>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th class="w-20">ID</th>
            <th>Пользователь</th>
            <th>device_id (thumbmarkjs)</th>
            <th>User-Agent</th>
            <th class="w-44">Создано</th>
            <th class="w-44">Активность</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in items" :key="d.id">
            <td>{{ d.id }}</td>
            <td>{{ userName(d.user_id) }}</td>
            <td class="max-w-56 truncate font-mono text-xs" :title="d.device_id">{{ d.device_id }}</td>
            <td class="max-w-64 truncate text-xs text-gray-500" :title="d.user_agent ?? ''">{{ d.user_agent || '—' }}</td>
            <td class="whitespace-nowrap">{{ formatDateTime(d.created_at) }}</td>
            <td class="whitespace-nowrap">{{ formatDateTime(d.last_seen_at) }}</td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="py-6 text-center text-gray-400">Устройств нет</td>
          </tr>
        </tbody>
      </table>
      <div class="px-4 pb-4">
        <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Device {
  id: number
  user_id: number
  device_id: string
  user_agent: string | null
  created_at: string
  last_seen_at: string
}
interface User {
  id: number
  username: string
}

const { page, pageAll } = useApi()

const users = ref<User[]>([])
const limit = PAGE_SIZE
const userId = ref('')
const { items, total, offset, load, changeOffset: goTo } = useListLoader<Device>((off, signal) => {
  const params: Record<string, unknown> = { limit, offset: off }
  if (userId.value) params.user_id = userId.value
  return page<Device>('/devices', params, signal)
}, limit)

function userName(id: number): string {
  return users.value.find((u) => u.id === id)?.username ?? `#${id}`
}

function changeOffset(v: number) {
  goTo(v, '[devices]')
}

onMounted(async () => {
  await load().catch((err) => showLoadError(err, '[devices]'))
  try {
    users.value = await pageAll<User>('/users')
  } catch (err) {
    console.warn('[devices] users load failed', err)
  }
})
</script>
