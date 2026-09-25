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
            <th class="w-40">Телефон</th>
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
            <td class="whitespace-nowrap">{{ v.phone || '—' }}</td>
            <td>{{ v.consent_given ? 'Да' : 'Нет' }}</td>
            <td>
              <span :class="v.is_blocked ? 'text-red-600' : 'text-green-600'">
                {{ v.is_blocked ? 'Заблокирован' : 'Активен' }}
              </span>
            </td>
            <td class="whitespace-nowrap">{{ formatDateTime(v.created_at) }}</td>
            <td>
              <button v-if="!v.is_blocked" class="btn-danger" :disabled="busyId === v.id" @click="ban(v)">Заблокировать</button>
              <button v-else class="btn-secondary" :disabled="busyId === v.id" @click="unban(v)">Разблокировать</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="7" class="py-6 text-center text-gray-400">Посетителей нет</td>
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
  phone: string | null
  consent_given: boolean
  is_blocked: boolean
  created_at: string
}

const { api, page } = useApi()

const limit = PAGE_SIZE
const search = ref('')
const blockedFilter = ref('')
// id посетителя, для которого выполняется бан/разбан (кнопка заблокирована)
const busyId = ref<number | null>(null)

const { items, total, offset, load, changeOffset: goTo } = useListLoader<Visitor>((off, signal) => {
  const params: Record<string, unknown> = { limit, offset: off }
  if (search.value.trim()) params.search = search.value.trim()
  if (blockedFilter.value !== '') params.is_blocked = blockedFilter.value === 'true'
  return page<Visitor>('/visitors', params, signal)
}, limit)

let timer: ReturnType<typeof setTimeout> | undefined
function debouncedLoad() {
  clearTimeout(timer)
  timer = setTimeout(() => changeOffset(0), 400)
}
// таймер не должен сработать после ухода со страницы
onBeforeUnmount(() => clearTimeout(timer))

function changeOffset(v: number) {
  goTo(v, '[visitors]')
}

async function ban(v: Visitor) {
  if (!confirm(`Заблокировать посетителя «${v.full_name}»?`)) return
  busyId.value = v.id
  try {
    await api(`/visitors/${v.id}/ban`, { method: 'POST' })
    await load()
  } catch (err) {
    console.warn('[visitors] ban failed', err)
    alert(apiErrorMessage(err, 'Не удалось заблокировать посетителя'))
  } finally {
    busyId.value = null
  }
}

async function unban(v: Visitor) {
  busyId.value = v.id
  try {
    await api(`/visitors/${v.id}/unban`, { method: 'POST' })
    await load()
  } catch (err) {
    console.warn('[visitors] unban failed', err)
    alert(apiErrorMessage(err, 'Не удалось разблокировать посетителя'))
  } finally {
    busyId.value = null
  }
}

await load().catch((err) => showLoadError(err, '[visitors]'))
</script>
