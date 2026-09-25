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
            <th>Поля заявки</th>
            <th>Статус</th>
            <th>Создана</th>
            <th class="w-56">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="req in items" :key="req.id">
            <td>#{{ req.id }}</td>
            <td>
              <NuxtLink
                :to="{ path: '/objects', query: { open: req.object_id } }"
                class="text-primary-600 hover:underline"
              >
                {{ objectName(req.object_id) }}
              </NuxtLink>
            </td>
            <td class="whitespace-nowrap">{{ req.phone }}</td>
            <td class="max-w-72">
              <template v-if="req.fields.length">
                <div
                  v-for="f in req.fields"
                  :key="f.field_id"
                  class="text-sm"
                  :title="`${f.field_label}: ${f.value ?? '—'}`"
                >
                  <span class="text-gray-500">{{ f.field_label }}:</span>
                  {{ f.value || '—' }}
                </div>
              </template>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td><StatusBadge :status="req.status" /></td>
            <td class="whitespace-nowrap">{{ formatDateTime(req.created_at) }}</td>
            <td class="space-x-2 whitespace-nowrap">
              <template v-if="canProcess(req)">
                <button v-if="req.status === 'new'" class="btn-primary" :disabled="busyId === req.id" @click="setStatus(req, 'approved')">
                  Подтвердить
                </button>
                <button v-if="req.status === 'new'" class="btn-danger" :disabled="busyId === req.id" @click="setStatus(req, 'rejected')">
                  Отклонить
                </button>
                <button v-if="req.status === 'approved'" class="btn-primary" :disabled="busyId === req.id" @click="setStatus(req, 'completed')">
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
interface ReqField {
  field_id: number
  field_code: string
  field_label: string
  value: string | null
}
interface Req {
  id: number
  visitor_id: number
  object_id: number
  phone: string
  fields: ReqField[]
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
const route = useRoute()
const { api, page, pageAll } = useApi()

const objects = ref<Obj[]>([])
const limit = PAGE_SIZE
const filters = ref({ status: '', objectId: '', dateFrom: '', dateTo: '' })
// id заявки, статус которой меняется (кнопки заблокированы)
const busyId = ref<number | null>(null)

/** Следующий календарный день (YYYY-MM-DD) для исключающей границы «по» */
function nextDay(value: string): string {
  const d = new Date(`${value}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}

const { items, total, offset, load, changeOffset: goTo } = useListLoader<Req>((off, signal) => {
  const params: Record<string, unknown> = { limit, offset: off }
  if (filters.value.status) params.status_filter = filters.value.status
  if (filters.value.objectId) params.object_id = filters.value.objectId
  // границы дня по Москве; «по» — исключающая: < 00:00 следующего дня
  if (filters.value.dateFrom) params.date_from = moscowToUtc(`${filters.value.dateFrom}T00:00`)
  if (filters.value.dateTo) params.date_to = moscowToUtc(`${nextDay(filters.value.dateTo)}T00:00`)
  return page<Req>('/requests', params, signal)
}, limit)

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

function changeOffset(v: number) {
  goTo(v, '[requests]')
}

function resetFilters() {
  filters.value = { status: '', objectId: '', dateFrom: '', dateTo: '' }
  changeOffset(0)
}

async function setStatus(req: Req, status: string) {
  const verb = status === 'approved' ? 'подтвердить' : status === 'rejected' ? 'отклонить' : 'пометить выполненной'
  if (!confirm(`${verb.charAt(0).toUpperCase() + verb.slice(1)} заявку #${req.id}?`)) return
  busyId.value = req.id
  try {
    await api(`/requests/${req.id}/status`, { method: 'POST', body: { status } })
    await load()
  } catch (err) {
    alert(apiErrorMessage(err, 'Не удалось изменить статус заявки'))
  } finally {
    busyId.value = null
  }
}

onMounted(async () => {
  // deep-link из дашборда: ?status=new — предустановить фильтр статуса
  const qs = route.query.status
  if (typeof qs === 'string' && ['new', 'approved', 'rejected', 'completed', 'cancelled_by_customer'].includes(qs)) {
    filters.value.status = qs
  }
  await load().catch((err) => showLoadError(err, '[requests]'))
  try {
    objects.value = await pageAll<Obj>('/objects')
  } catch (err) {
    console.warn('[requests] objects load failed', err)
  }
})
</script>
