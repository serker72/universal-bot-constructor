<template>
  <div>
    <h1 class="page-title mb-4">Заявки</h1>

    <!-- Фильтры -->
    <div class="card mb-4 grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-5">
      <div>
        <label class="label" for="f-status">Статус</label>
        <select id="f-status" v-model="filters.status" class="input" @change="changeOffset(0)">
          <option value="">Все</option>
          <option value="new">Новые</option>
          <option value="approved">Подтверждённые</option>
          <option value="rejected">Отклонённые</option>
          <option value="completed">Выполненные</option>
          <option value="cancelled_by_customer">Отменённые</option>
        </select>
      </div>
      <div>
        <label class="label" for="f-object">Объект</label>
        <select id="f-object" v-model="filters.objectId" class="input" @change="changeOffset(0)">
          <option value="">Все объекты</option>
          <option v-for="obj in objects" :key="obj.id" :value="obj.id">{{ obj.name }}</option>
        </select>
      </div>
      <div>
        <label class="label" for="f-from">Дата с</label>
        <input id="f-from" v-model="filters.dateFrom" class="input" type="date" @change="changeOffset(0)" />
      </div>
      <div>
        <label class="label" for="f-to">Дата по</label>
        <input id="f-to" v-model="filters.dateTo" class="input" type="date" @change="changeOffset(0)" />
      </div>
      <div class="flex items-end">
        <button class="btn-secondary" @click="resetFilters">Сбросить</button>
      </div>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th class="w-20">№</th>
            <th>Объект</th>
            <th>Телефон</th>
            <th>Комментарий</th>
            <th>Статус</th>
            <th>Создана</th>
            <th class="w-56">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="req in items" :key="req.id">
            <td>#{{ req.id }}</td>
            <td>{{ objectName(req.object_id) }}</td>
            <td class="whitespace-nowrap">{{ req.phone }}</td>
            <td class="max-w-56 truncate" :title="req.comment ?? ''">{{ req.comment || '—' }}</td>
            <td><StatusBadge :status="req.status" /></td>
            <td class="whitespace-nowrap">{{ formatDateTime(req.created_at) }}</td>
            <td class="space-x-2 whitespace-nowrap">
              <template v-if="canProcess(req)">
                <button v-if="req.status === 'new'" class="btn-primary" @click="setStatus(req, 'approved')">
                  Подтвердить
                </button>
                <button v-if="req.status === 'new'" class="btn-danger" @click="setStatus(req, 'rejected')">
                  Отклонить
                </button>
                <button v-if="req.status === 'approved'" class="btn-primary" @click="setStatus(req, 'completed')">
                  Выполнена
                </button>
              </template>
              <span v-else class="text-gray-400">—</span>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="7" class="py-6 text-center text-gray-400">Заявок нет</td>
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
interface Req {
  id: number
  visitor_id: number
  object_id: number
  phone: string
  comment: string | null
  status: string
  confirmed_at: string | null
  created_at: string
  updated_at: string
}
interface Obj {
  id: number
  name: string
}

const auth = useAuth()
const { api, page } = useApi()

const items = ref<Req[]>([])
const objects = ref<Obj[]>([])
const total = ref(0)
const limit = PAGE_SIZE
const offset = ref(0)
const filters = ref({ status: '', objectId: '', dateFrom: '', dateTo: '' })

function objectName(id: number): string {
  return objects.value.find((o) => o.id === id)?.name ?? `#${id}`
}

/** Обработка доступна только менеджеру объекта: new → approved/rejected, approved → completed */
function canProcess(req: Req): boolean {
  if (!auth.isAdmin.value) {
    return req.status === 'new' || req.status === 'approved'
  }
  return false
}

async function load() {
  const params: Record<string, unknown> = { limit, offset: offset.value }
  if (filters.value.status) params.status_filter = filters.value.status
  if (filters.value.objectId) params.object_id = filters.value.objectId
  if (filters.value.dateFrom) params.date_from = `${filters.value.dateFrom}T00:00:00+03:00`
  if (filters.value.dateTo) params.date_to = `${filters.value.dateTo}T23:59:59+03:00`
  const p = await page<Req>('/requests', params)
  items.value = p.items
  total.value = p.total
}

function changeOffset(v: number) {
  offset.value = v
  load()
}

function resetFilters() {
  filters.value = { status: '', objectId: '', dateFrom: '', dateTo: '' }
  changeOffset(0)
}

async function setStatus(req: Req, status: string) {
  const verb = status === 'approved' ? 'подтвердить' : status === 'rejected' ? 'отклонить' : 'пометить выполненной'
  if (!confirm(`${verb.charAt(0).toUpperCase() + verb.slice(1)} заявку #${req.id}?`)) return
  try {
    await api(`/requests/${req.id}/status`, { method: 'POST', body: { status } })
    await load()
  } catch {
    alert('Не удалось изменить статус заявки')
  }
}

onMounted(async () => {
  await load()
  try {
    const p = await page<Obj>('/objects', { limit: 1000 })
    objects.value = p.items
  } catch {
    /* фильтр по объекту не критичен */
  }
})
</script>
