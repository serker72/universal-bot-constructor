<template>
  <div>
    <h1 class="page-title mb-4">Сессии</h1>

    <div class="card mb-4 flex flex-wrap items-end gap-4 p-4">
      <div class="w-64">
        <label class="label" for="s-user">Фильтр по пользователю</label>
        <select id="s-user" v-model="userId" class="input" @change="changeOffset(0)">
          <option value="">Все пользователи</option>
          <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
        </select>
      </div>
      <label class="flex items-center gap-2 pb-2 text-sm">
        <input v-model="onlyActive" type="checkbox" class="h-4 w-4" @change="changeOffset(0)" />
        Только активные
      </label>
      <div class="grow" />
      <div v-if="userId" class="pb-1">
        <button class="btn-danger" @click="revokeAll">Отозвать все сессии пользователя</button>
      </div>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th class="w-20">ID</th>
            <th>Пользователь</th>
            <th>Устройство</th>
            <th>JTI (refresh)</th>
            <th class="w-28">Статус</th>
            <th class="w-44">Создана</th>
            <th class="w-44">Отозвана</th>
            <th class="w-32">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in items" :key="s.id">
            <td>{{ s.id }}</td>
            <td>{{ userName(s.user_id) }}</td>
            <td>{{ s.device_id }}</td>
            <td class="max-w-48 truncate font-mono text-xs" :title="s.refresh_token_jti">{{ s.refresh_token_jti }}</td>
            <td>
              <UiBoolBadge :value="s.is_active" yes-text="Активна" no-text="Отозвана" />
            </td>
            <td class="whitespace-nowrap">{{ formatDateTime(s.created_at) }}</td>
            <td class="whitespace-nowrap">{{ formatDateTime(s.revoked_at) }}</td>
            <td>
              <button v-if="s.is_active" class="btn-danger" @click="revoke(s)">Отозвать</button>
              <span v-else class="text-gray-400">—</span>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="8" class="py-6 text-center text-gray-400">Сессий нет</td>
          </tr>
        </tbody>
      </table>
      <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Session, User } from '~/types/models'

const { api, page, pageAll } = useApi()

const users = ref<User[]>([])
const limit = PAGE_SIZE
const userId = ref('')
const onlyActive = ref(false)
const { items, total, offset, load, changeOffset: goTo } = useListLoader<Session>((off, signal) => {
  const params: Record<string, unknown> = { limit, offset: off }
  if (userId.value) params.user_id = userId.value
  if (onlyActive.value) params.only_active = true
  return page<Session>('/sessions', params, signal)
}, limit)

function userName(id: number): string {
  return nameById(users.value, id)
}

function changeOffset(v: number) {
  goTo(v, '[sessions]')
}

async function revoke(s: Session) {
  if (!confirm(`Отозвать сессию #${s.id}?`)) return
  try {
    await api(`/sessions/${s.id}/revoke`, { method: 'POST' })
    await load()
  } catch (err) {
    alert(apiErrorMessage(err, 'Не удалось отозвать сессию'))
  }
}

async function revokeAll() {
  if (!confirm(`Отозвать ВСЕ сессии пользователя ${userName(Number(userId.value))}?`)) return
  try {
    await api(`/sessions/users/${userId.value}/revoke-all`, { method: 'POST' })
    await load()
  } catch (err) {
    alert(apiErrorMessage(err, 'Не удалось отозвать сессии'))
  }
}

onMounted(async () => {
  await load().catch((err) => showLoadError(err, '[sessions]'))
  try {
    users.value = await pageAll<User>('/users')
  } catch (err) {
    console.warn('[sessions] users load failed', err)
  }
})
</script>
