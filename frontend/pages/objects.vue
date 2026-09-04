<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h1 class="page-title">Объекты</h1>
      <button class="btn-primary" @click="openCreate">Добавить</button>
    </div>

    <div class="mb-4 max-w-xs">
      <label class="label" for="obj-cat">Фильтр по категории</label>
      <select id="obj-cat" v-model="filterCategory" class="input" @change="changeOffset(0)">
        <option :value="null">Все категории</option>
        <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
      </select>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th>Название</th>
            <th>Категория</th>
            <th class="w-24">Порядок</th>
            <th class="w-24">Активен</th>
            <th class="w-28">PDF</th>
            <th class="w-56">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="obj in items" :key="obj.id">
            <td class="font-medium">{{ obj.name }}</td>
            <td>{{ categoryName(obj.category_id) }}</td>
            <td>{{ obj.sort_order }}</td>
            <td>
              <span :class="obj.is_active ? 'text-green-600' : 'text-gray-400'">
                {{ obj.is_active ? 'Да' : 'Нет' }}
              </span>
            </td>
            <td>
              <span :class="obj.has_pdf ? 'text-green-600' : 'text-gray-400'">
                {{ obj.has_pdf ? 'Есть' : 'Нет' }}
              </span>
            </td>
            <td class="space-x-2 whitespace-nowrap">
              <button v-if="obj.has_pdf" class="btn-secondary" @click="openPdf(obj)">PDF</button>
              <button class="btn-secondary" @click="openEdit(obj)">Изменить</button>
              <button class="btn-secondary" @click="openManagers(obj)">Менеджеры</button>
              <button class="btn-danger" @click="remove(obj)">Удалить</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="py-6 text-center text-gray-400">Объектов пока нет</td>
          </tr>
        </tbody>
      </table>
      <div class="px-4 pb-4">
        <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
      </div>
    </div>

    <!-- Редактирование объекта -->
    <UiModal :open="modal" :title="form.id ? 'Изменить объект' : 'Новый объект'" @close="modal = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label" for="form-cat">Категория</label>
          <select id="form-cat" v-model.number="form.category_id" class="input" required>
            <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
        </div>
        <div>
          <label class="label" for="form-name">Название</label>
          <input id="form-name" v-model="form.name" class="input" required maxlength="255" />
        </div>
        <div>
          <label class="label" for="form-desc">Краткое описание (HTML/Markdown)</label>
          <textarea id="form-desc" v-model="form.short_description" class="input min-h-24"></textarea>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label" for="form-sort">Порядок</label>
            <input id="form-sort" v-model.number="form.sort_order" class="input" type="number" />
          </div>
          <label class="mt-6 flex items-center gap-2 text-sm">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4" />
            Активен
          </label>
        </div>

        <!-- PDF: при создании загрузится сразу после сохранения -->
        <div>
          <label class="label" for="form-pdf">
            PDF-файл (до 20 МБ)<span v-if="!form.id" class="font-normal text-gray-400"> — загрузится после сохранения</span>
          </label>
          <input
            id="form-pdf"
            type="file"
            accept="application/pdf,.pdf"
            class="input"
            @change="pdfFile = $event.target.files?.[0] ?? null"
          />
          <p v-if="form.id && form.has_pdf && !pdfFile" class="mt-1 text-xs text-green-600">
            PDF загружен. Можно заменить, выбрав новый файл.
          </p>
          <button
            v-if="form.id && pdfFile"
            class="btn-secondary mt-2"
            type="button"
            :disabled="uploading"
            @click="uploadPdf"
          >
            {{ uploading ? 'Загрузка…' : 'Загрузить PDF' }}
          </button>
        </div>

        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" type="button" @click="modal = false">Отмена</button>
          <button class="btn-primary" type="submit" :disabled="saving">Сохранить</button>
        </div>
      </form>
    </UiModal>

    <!-- Назначение менеджеров -->
    <UiModal :open="managersModal" title="Менеджеры объекта" @close="managersModal = false">
      <p v-if="!managers.length" class="mb-3 text-sm text-gray-500">
        Нет активных пользователей с ролью «менеджер».
      </p>
      <div class="mb-4 max-h-64 space-y-2 overflow-y-auto">
        <label v-for="m in managers" :key="m.id" class="flex items-center gap-2 text-sm">
          <input v-model="selectedManagers" type="checkbox" :value="m.id" class="h-4 w-4" />
          {{ m.username }}
        </label>
      </div>
      <p v-if="managersError" class="mb-2 text-sm text-red-600">{{ managersError }}</p>
      <div class="flex justify-end gap-2">
        <button class="btn-secondary" type="button" @click="managersModal = false">Отмена</button>
        <button class="btn-primary" type="button" :disabled="managersSaving" @click="saveManagers">
          Сохранить
        </button>
      </div>
    </UiModal>
  </div>
</template>

<script setup lang="ts">
interface Category {
  id: number
  name: string
}
interface Obj {
  id: number
  category_id: number
  name: string
  short_description: string
  sort_order: number
  is_active: boolean
  has_pdf: boolean
}
interface Manager {
  id: number
  username: string
  role: 'admin' | 'manager'
  is_active: boolean
}

const { api, page, baseURL } = useApi()

const categories = ref<Category[]>([])
const items = ref<Obj[]>([])
const total = ref(0)
const limit = PAGE_SIZE
const offset = ref(0)
const filterCategory = ref<number | null>(null)

const modal = ref(false)
const saving = ref(false)
const uploading = ref(false)
const formError = ref('')
const pdfFile = ref<File | null>(null)
const form = ref({ id: 0, category_id: 0, name: '', short_description: '', sort_order: 0, is_active: true })

const managersModal = ref(false)
const managers = ref<Manager[]>([])
const selectedManagers = ref<number[]>([])
const managersSaving = ref(false)
const managersError = ref('')
const managersObjectId = ref(0)

function categoryName(id: number): string {
  return categories.value.find((c) => c.id === id)?.name ?? `#${id}`
}

async function load() {
  const params: Record<string, unknown> = { limit, offset: offset.value }
  if (filterCategory.value !== null) params.category_id = filterCategory.value
  const p = await page<Obj>('/objects', params)
  items.value = p.items
  total.value = p.total
}

function changeOffset(v: number) {
  offset.value = v
  load()
}

function openCreate() {
  form.value = {
    id: 0,
    category_id: categories.value[0]?.id ?? 0,
    name: '',
    short_description: '',
    sort_order: items.value.length,
    is_active: true,
  }
  pdfFile.value = null
  formError.value = ''
  modal.value = true
}

function openEdit(obj: Obj) {
  form.value = { ...obj }
  pdfFile.value = null
  formError.value = ''
  modal.value = true
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    const body = {
      category_id: form.value.category_id,
      name: form.value.name,
      short_description: form.value.short_description,
      sort_order: form.value.sort_order,
      is_active: form.value.is_active,
    }
    let object_id = form.value.id
    if (object_id) {
      await api(`/objects/${object_id}`, { method: 'PATCH', body })
    } else {
      const created = await api<Obj>('/objects', { method: 'POST', body })
      object_id = created.id
    }
    // выбранный PDF загружаем сразу после сохранения (в т.ч. при создании)
    if (pdfFile.value && object_id) {
      const fd = new FormData()
      fd.append('file', pdfFile.value)
      await api(`/objects/${object_id}/pdf`, { method: 'PUT', body: fd })
    }
    modal.value = false
    await load()
  } catch {
    formError.value = 'Не удалось сохранить объект (проверьте PDF: только PDF, до 20 МБ)'
  } finally {
    saving.value = false
  }
}

async function uploadPdf() {
  if (!pdfFile.value || !form.value.id) return
  uploading.value = true
  formError.value = ''
  try {
    const fd = new FormData()
    fd.append('file', pdfFile.value)
    await api(`/objects/${form.value.id}/pdf`, { method: 'PUT', body: fd })
    pdfFile.value = null
    await load()
    modal.value = false
  } catch {
    formError.value = 'Не удалось загрузить PDF (только PDF, до 20 МБ)'
  } finally {
    uploading.value = false
  }
}

function openPdf(obj: Obj) {
  // авторизация — httpOnly cookies, открывается в новой вкладке
  window.open(`${baseURL}/objects/${obj.id}/pdf`, '_blank')
}

async function openManagers(obj: Obj) {
  managersObjectId.value = obj.id
  managersError.value = ''
  managersModal.value = true
  try {
    const out = await api<{ object_id: number; user_ids: number[] }>(`/objects/${obj.id}/managers`)
    selectedManagers.value = [...out.user_ids]
  } catch {
    managersError.value = 'Не удалось загрузить менеджеров'
  }
}

async function saveManagers() {
  managersSaving.value = true
  managersError.value = ''
  try {
    await api(`/objects/${managersObjectId.value}/managers`, {
      method: 'PUT',
      body: { user_ids: selectedManagers.value },
    })
    managersModal.value = false
  } catch {
    managersError.value = 'Не удалось сохранить менеджеров'
  } finally {
    managersSaving.value = false
  }
}

async function remove(obj: Obj) {
  if (!confirm(`Удалить объект «${obj.name}»?`)) return
  try {
    await api(`/objects/${obj.id}`, { method: 'DELETE' })
    await load()
  } catch {
    alert('Не удалось удалить объект')
  }
}

onMounted(async () => {
  try {
    const p = await page<Category>('/categories', { limit: 1000 })
    categories.value = p.items
  } catch {
    /* категории нужны для фильтра/формы */
  }
  await load()
  // менеджеры для модалки назначения
  try {
    const p = await page<Manager>('/users', { limit: 1000 })
    managers.value = p.items.filter((u) => u.role === 'manager' && u.is_active)
  } catch {
    /* не критично */
  }
})
</script>
