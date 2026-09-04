<template>
  <div>
    <h1 class="page-title mb-4">Посетители</h1>

    <div class="card mb-4 grid grid-cols-1 gap-4 p-4 sm:grid-cols-3">
      <div>
        <label class="label" for="v-search">Поиск по ФИО</label>
        <input id="v-search" v-model="search" class="input" type="text" @input="debouncedLoad" />
      </div>
      <div>
        <label class="label" for="v-blocked">Блокировка</label>
        <select id="v-blocked" v-model="blockedFilter" class="input" @change="changeOffset(0)">
          <option value="">Все</option>
          <option value="false">Активные</option>
          <option value="true">Заблокированные</option>
        </select>
      </div>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th>ФИО</th>
            <th class="w-40">Telegram ID</th>
            <th class="w-28">Согласие</th>
            <th class="w-36">Статус</th>
            <th class="w-44">Зарегистрирован</th>
            <th class="w-40">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in items" :key="v.id">
            <td class="font-medium">{{ v.full_name }}</td>
            <td>{{ v.telegram_id }}</td>
            <td>{{ v.consent_given ? 'Да' : 'Нет' }}</td>
            <td>
              <span :class="v.is_blocked ? 'text-red-600' : 'text-green-600'">
                {{ v.is_blocked ? 'Заблокирован' : 'Активен' }}
              </span>
            </td>
            <td class="whitespace-nowrap">{{ formatDateTime(v.created_at) }}</td>
            <td>
              <button v-if="!v.is_blocked" class="btn-danger" @click="ban(v)">Заблокировать</button>
              <button v-else class="btn-secondary" @click="unban(v)">Разблокировать</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="py-6 text-center text-gray-400">Посетителей нет</td>
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
interface Visitor {
  id: number
  telegram_id: number
  full_name: string
  consent_given: boolean
  is_blocked: boolean
  created_at: string
}

const { api, page } = useApi()

const items = ref<Visitor[]>([])
const total = ref(0)
const limit = PAGE_SIZE
const offset = ref(0)
const search = ref('')
const blockedFilter = ref('')

let timer: ReturnType<typeof setTimeout> | undefined
function debouncedLoad() {
  clearTimeout(timer)
  timer = setTimeout(() => changeOffset(0), 400)
}

async function load() {
  const params: Record<string, unknown> = { limit, offset: offset.value }
  if (search.value.trim()) params.search = search.value.trim()
  if (blockedFilter.value !== '') params.is_blocked = blockedFilter.value === 'true'
  const p = await page<Visitor>('/visitors', params)
  items.value = p.items
  total.value = p.total
}

function changeOffset(v: number) {
  offset.value = v
  load()
}

async function ban(v: Visitor) {
  if (!confirm(`Заблокировать посетителя «${v.full_name}»?`)) return
  try {
    await api(`/visitors/${v.id}/ban`, { method: 'POST' })
    await load()
  } catch {
    alert('Не удалось заблокировать посетителя')
  }
}

async function unban(v: Visitor) {
  try {
    await api(`/visitors/${v.id}/unban`, { method: 'POST' })
    await load()
  } catch {
    alert('Не удалось разблокировать посетителя')
  }
}

await load()
</script>
