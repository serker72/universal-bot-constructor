<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h1 class="page-title">Объекты</h1>
      <button v-if="isAdmin" class="btn-primary" @click="openCreate">Добавить</button>
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
              <UiBoolBadge :value="obj.is_active" />
            </td>
            <td>
              <UiBoolBadge :value="obj.has_pdf" yes-text="Есть" no-text="Нет" />
            </td>
            <td class="space-x-2 whitespace-nowrap">
              <button v-if="obj.has_pdf" class="btn-secondary" @click="openPdf(obj)">PDF</button>
              <template v-if="isAdmin">
                <button class="btn-secondary" @click="openEdit(obj)">Изменить</button>
                <button class="btn-secondary" @click="openManagers(obj)">Менеджеры</button>
                <button class="btn-danger" @click="remove(obj)">Удалить</button>
              </template>
              <button v-else class="btn-secondary" @click="openView(obj)">Просмотр</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="py-6 text-center text-gray-400">Объектов пока нет</td>
          </tr>
        </tbody>
      </table>
      <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
    </div>

    <!-- Редактирование объекта (manager — режим просмотра) -->
    <UiModal
      :open="modal"
      :title="readOnly ? 'Объект' : form.id ? 'Изменить объект' : 'Новый объект'"
      @close="modal = false"
    >
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label" for="form-cat">Категория</label>
          <select id="form-cat" v-model.number="form.category_id" class="input" required :disabled="readOnly">
            <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
        </div>
        <div>
          <label class="label" for="form-name">Название</label>
          <input id="form-name" v-model="form.name" class="input" required maxlength="255" :disabled="readOnly" />
        </div>
        <div>
          <label class="label" for="form-desc">Краткое описание (HTML)</label>
          <textarea id="form-desc" v-model="form.short_description" class="input min-h-24" :disabled="readOnly"></textarea>
          <p class="mt-1 text-xs text-gray-400">
            Допустимые теги: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;s&gt;, &lt;code&gt;, &lt;pre&gt;, &lt;a&gt;, &lt;blockquote&gt;, &lt;tg-spoiler&gt;
          </p>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label" for="form-sort">Порядок</label>
            <input id="form-sort" v-model.number="form.sort_order" class="input" type="number" :disabled="readOnly" />
          </div>
          <label class="mt-6 flex items-center gap-2 text-sm">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4" :disabled="readOnly" />
            Активен
          </label>
        </div>

        <!-- PDF: при создании загрузится сразу после сохранения -->
        <div v-if="!readOnly">
          <label class="label" for="form-pdf">
            PDF-файл (до 20 МБ)<span v-if="!form.id" class="font-normal text-gray-400"> — загрузится после сохранения</span>
          </label>
          <input
            id="form-pdf"
            ref="pdfInput"
            type="file"
            accept="application/pdf,.pdf"
            class="input"
            @change="pdfFile = ($event.target as HTMLInputElement).files?.[0] ?? null"
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
          <button class="btn-secondary" type="button" @click="modal = false">
            {{ readOnly ? 'Закрыть' : 'Отмена' }}
          </button>
          <button
            v-if="readOnly && form.has_pdf"
            class="btn-primary"
            type="button"
            @click="openPdf({ id: form.id } as Obj)"
          >
            Открыть PDF
          </button>
          <button v-else-if="!readOnly" class="btn-primary" type="submit" :disabled="saving">
            Сохранить
          </button>
        </div>
      </form>
    </UiModal>

    <!-- Назначение менеджеров -->
    <UiManagersModal
      :open="managersModal"
      :endpoint="`/objects/${managersObjectId}`"
      title="Менеджеры объекта"
      @close="managersModal = false"
    />
  </div>
</template>

<script setup lang="ts">
import type { Category, Obj } from '~/types/models'

const { api, page, pageAll, baseURL } = useApi()
const auth = useAuth()
const isAdmin = auth.isAdmin
const route = useRoute()
const router = useRouter()

const categories = ref<Category[]>([])
const limit = PAGE_SIZE
const filterCategory = ref<number | null>(null)
const { items, total, offset, load, changeOffset: goTo } = useListLoader<Obj>((off, signal) => {
  const params: Record<string, unknown> = { limit, offset: off }
  if (filterCategory.value !== null) params.category_id = filterCategory.value
  return page<Obj>('/objects', params, signal)
}, limit)
const pdfInput = ref<HTMLInputElement | null>(null)

const modal = ref(false)
const readOnly = ref(false)
const saving = ref(false)
const uploading = ref(false)
const formError = ref('')
const pdfFile = ref<File | null>(null)
const form = ref({ id: 0, category_id: 0, name: '', short_description: '', sort_order: 0, is_active: true, has_pdf: false })

// модалка UiManagersModal: id объекта нужен только для endpoint
const managersModal = ref(false)
const managersObjectId = ref(0)

function categoryName(id: number): string {
  return nameById(categories.value, id)
}

function changeOffset(v: number) {
  goTo(v, '[objects]')
}

/** Сброс выбранного PDF (и значения file input — иначе тот же файл не выбрать повторно) */
function resetPdfInput() {
  pdfFile.value = null
  if (pdfInput.value) pdfInput.value.value = ''
}

function openCreate() {
  form.value = {
    id: 0,
    category_id: categories.value[0]?.id ?? 0,
    name: '',
    short_description: '',
    sort_order: items.value.length,
    is_active: true,
    has_pdf: false,
  }
  readOnly.value = false
  resetPdfInput()
  formError.value = ''
  modal.value = true
}

function openEdit(obj: Obj) {
  form.value = { ...obj }
  readOnly.value = false
  resetPdfInput()
  formError.value = ''
  modal.value = true
}

/** Режим просмотра (manager, deep-link из заявок) */
function openView(obj: Obj) {
  form.value = { ...obj }
  readOnly.value = true
  resetPdfInput()
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
    if (form.value.id) {
      await api(`/objects/${form.value.id}`, { method: 'PATCH', body })
    } else {
      const created = await api<Obj>('/objects', { method: 'POST', body })
      // id — в форму сразу: повторное «Сохранить» после ошибки загрузки PDF
      // делает PATCH, а не второй POST (дубликат объекта)
      form.value.id = created.id
    }
    // выбранный PDF загружаем сразу после сохранения (в т.ч. при создании)
    if (pdfFile.value && form.value.id) {
      const fd = new FormData()
      fd.append('file', pdfFile.value)
      await api(`/objects/${form.value.id}/pdf`, { method: 'PUT', body: fd })
      resetPdfInput()
    }
    modal.value = false
    await load()
  } catch (err) {
    console.warn('[objects] save failed', err)
    formError.value = apiErrorMessage(
      err,
      'Не удалось сохранить объект (проверьте PDF: только PDF, до 20 МБ)',
    )
    // объект мог быть создан до ошибки PDF — обновить список
    load().catch(() => {})
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
    resetPdfInput()
    await load()
    modal.value = false
  } catch (err) {
    console.warn('[objects] pdf upload failed', err)
    formError.value = apiErrorMessage(err, 'Не удалось загрузить PDF (только PDF, до 20 МБ)')
  } finally {
    uploading.value = false
  }
}

function openPdf(obj: Obj) {
  // авторизация — httpOnly cookies, открывается в новой вкладке
  window.open(`${baseURL}/objects/${obj.id}/pdf`, '_blank')
}

function openManagers(obj: Obj) {
  managersObjectId.value = obj.id
  managersModal.value = true
}

async function remove(obj: Obj) {
  if (!confirm(`Удалить объект «${obj.name}»?`)) return
  try {
    await api(`/objects/${obj.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    console.warn('[objects] delete failed', err)
    alert(apiErrorMessage(err, 'Не удалось удалить объект'))
  }
}

/** Deep-link /objects?open={id} — открыть карточку объекта (режим просмотра) */
async function openFromQuery() {
  const raw = Number(route.query.open)
  if (!Number.isInteger(raw) || raw <= 0) return
  // убираем параметр, чтобы модалка не открывалась повторно при навигации
  router.replace({ path: '/objects', query: {} })
  let obj = items.value.find((o) => o.id === raw)
  if (!obj) {
    try {
      obj = await api<Obj>(`/objects/${raw}`)
    } catch (err) {
      // объект недоступен (чужой/удалён) — остаёмся на списке
      console.warn('[objects] deep-link object not available', err)
      return
    }
  }
  openView(obj)
}

onMounted(async () => {
  try {
    categories.value = await pageAll<Category>('/categories')
  } catch (err) {
    // категории нужны для фильтра/формы
    console.warn('[objects] failed to load categories', err)
  }
  try {
    await load()
  } catch (err) {
    showLoadError(err, '[objects]')
  }
  await openFromQuery()
})
</script>
