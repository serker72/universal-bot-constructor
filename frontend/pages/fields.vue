<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h1 class="page-title">Поля заявки</h1>
      <button class="btn-primary" @click="openCreate">Добавить поле</button>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th>Код</th>
            <th>Тип</th>
            <th>Подпись</th>
            <th class="w-28">Обязательное</th>
            <th>Параметры</th>
            <th class="w-40">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in items" :key="f.id">
            <td class="font-mono text-sm">{{ f.code }}</td>
            <td>
              <span class="rounded bg-gray-100 px-2 py-0.5 text-xs">
                {{ TYPE_LABELS[f.type] || f.type }}
              </span>
            </td>
            <td class="font-medium">{{ f.label }}</td>
            <td>{{ f.is_required_default ? 'Да' : 'Нет' }}</td>
            <td class="max-w-xs truncate font-mono text-xs text-gray-500">
              {{ metaText(f) }}
            </td>
            <td class="space-x-2 whitespace-nowrap">
              <button class="btn-secondary" @click="openEdit(f)">Изменить</button>
              <button class="btn-danger" @click="remove(f)">Удалить</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="py-6 text-center text-gray-400">
              Полей пока нет. Добавьте поля, затем привяжите их к категориям.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <UiModal :open="modal" :title="form.id ? 'Изменить поле' : 'Новое поле'" @close="modal = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label" for="fld-code">Код (латиница, подчёркивание)</label>
          <input id="fld-code" v-model="form.code" class="input" required maxlength="64"
                 pattern="[a-z0-9_]+" placeholder="delivery_time" />
        </div>
        <div>
          <label class="label" for="fld-type">Тип поля</label>
          <select id="fld-type" v-model="form.type" class="input">
            <option v-for="(label, value) in TYPE_LABELS" :key="value" :value="value">
              {{ label }}
            </option>
          </select>
        </div>
        <div>
          <label class="label" for="fld-label">Подпись (видна посетителю в боте)</label>
          <input id="fld-label" v-model="form.label" class="input" required maxlength="255" />
        </div>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="form.is_required_default" type="checkbox" class="h-4 w-4" />
          Обязательное по умолчанию
        </label>

        <!-- Параметры по типу -->
        <div v-if="form.type === 'select'" class="space-y-2">
          <label class="label" for="fld-options">Варианты (по одному в строке)</label>
          <textarea id="fld-options" v-model="optionsText" class="input min-h-24"
                    placeholder="Вариант 1&#10;Вариант 2" />
        </div>
        <div v-else-if="form.type === 'time'" class="space-y-2">
          <label class="label" for="fld-step">Шаг минут (делитель 60: 1, 5, 10, 15, 30)</label>
          <input id="fld-step" v-model.number="minuteStep" class="input" type="number" min="1" max="30" />
        </div>
        <div v-else-if="form.type === 'number'" class="grid grid-cols-2 gap-4">
          <div>
            <label class="label" for="fld-min">Минимум</label>
            <input id="fld-min" v-model.number="numMin" class="input" type="number" />
          </div>
          <div>
            <label class="label" for="fld-max">Максимум</label>
            <input id="fld-max" v-model.number="numMax" class="input" type="number" />
          </div>
        </div>
        <div v-else-if="form.type === 'text'" class="space-y-2">
          <label class="label" for="fld-maxlen">Максимальная длина</label>
          <input id="fld-maxlen" v-model.number="maxLength" class="input" type="number" min="1" max="1000" />
        </div>

        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" type="button" @click="modal = false">Отмена</button>
          <button class="btn-primary" type="submit" :disabled="saving">Сохранить</button>
        </div>
      </form>
    </UiModal>
  </div>
</template>

<script setup lang="ts">
interface Field {
  id: number
  code: string
  type: 'text' | 'number' | 'date' | 'time' | 'select'
  label: string
  is_required_default: boolean
  meta_data: Record<string, unknown> | null
}

const TYPE_LABELS: Record<string, string> = {
  text: 'Текст',
  number: 'Число',
  date: 'Дата',
  time: 'Время (часы и минуты)',
  select: 'Выбор из вариантов',
}

const { api, pageAll } = useApi()

const items = ref<Field[]>([])
const modal = ref(false)
const saving = ref(false)
const formError = ref('')
const form = ref({
  id: 0,
  code: '',
  type: 'text' as Field['type'],
  label: '',
  is_required_default: false,
})
// параметры по типу (meta_data)
const optionsText = ref('')
// v-model.number: при очистке поля значение — "" (см. isNumber)
const minuteStep = ref<number | ''>(5)
const numMin = ref<number | '' | null>(null)
const numMax = ref<number | '' | null>(null)
const maxLength = ref<number | ''>(1000)

function metaText(f: Field): string {
  if (!f.meta_data) return '—'
  return JSON.stringify(f.meta_data)
}

function applyMeta(f: Field | null) {
  const meta = (f?.meta_data ?? {}) as Record<string, unknown>
  optionsText.value = Array.isArray(meta.options) ? (meta.options as string[]).join('\n') : ''
  minuteStep.value = typeof meta.minute_step === 'number' ? meta.minute_step : 5
  numMin.value = typeof meta.min === 'number' ? meta.min : null
  numMax.value = typeof meta.max === 'number' ? meta.max : null
  maxLength.value = typeof meta.max_length === 'number' ? meta.max_length : 1000
}

function buildMeta(): Record<string, unknown> | null {
  const meta: Record<string, unknown> = {}
  if (form.value.type === 'select') {
    const options = optionsText.value.split('\n').map((s) => s.trim()).filter(Boolean)
    if (!options.length) return null
    meta.options = options
  } else if (form.value.type === 'time') {
    if (isNumber(minuteStep.value)) meta.minute_step = minuteStep.value
  } else if (form.value.type === 'number') {
    if (isNumber(numMin.value)) meta.min = numMin.value
    if (isNumber(numMax.value)) meta.max = numMax.value
  } else if (form.value.type === 'text') {
    if (isNumber(maxLength.value)) meta.max_length = maxLength.value
  }
  return Object.keys(meta).length ? meta : null
}

/** Число из v-model.number: очищенное поле даёт "" (или NaN) — это не число */
function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Проверка параметров до отправки (backend проверяет то же самое) */
function metaError(): string {
  if (form.value.type === 'time') {
    const step = minuteStep.value
    if (!isNumber(step) || !Number.isInteger(step) || step < 1 || step > 30 || 60 % step !== 0) {
      return 'Шаг минут — делитель 60: 1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30'
    }
  } else if (form.value.type === 'number') {
    if (isNumber(numMin.value) && isNumber(numMax.value) && numMin.value > numMax.value) {
      return 'Минимум не может быть больше максимума'
    }
  } else if (form.value.type === 'text') {
    const len = maxLength.value
    if (isNumber(len) && (!Number.isInteger(len) || len < 1 || len > 1000)) {
      return 'Максимальная длина — целое число 1..1000'
    }
  }
  return ''
}

async function load() {
  items.value = await pageAll<Field>('/request-fields')
}

function openCreate() {
  form.value = { id: 0, code: '', type: 'text', label: '', is_required_default: false }
  applyMeta(null)
  formError.value = ''
  modal.value = true
}

function openEdit(f: Field) {
  form.value = {
    id: f.id,
    code: f.code,
    type: f.type,
    label: f.label,
    is_required_default: f.is_required_default,
  }
  applyMeta(f)
  formError.value = ''
  modal.value = true
}

async function save() {
  saving.value = true
  formError.value = ''
  const meta = buildMeta()
  if (form.value.type === 'select' && !meta) {
    formError.value = 'Укажите хотя бы один вариант'
    saving.value = false
    return
  }
  const invalid = metaError()
  if (invalid) {
    formError.value = invalid
    saving.value = false
    return
  }
  try {
    const body = {
      code: form.value.code,
      type: form.value.type,
      label: form.value.label,
      is_required_default: form.value.is_required_default,
      meta_data: meta,
    }
    if (form.value.id) {
      await api(`/request-fields/${form.value.id}`, { method: 'PATCH', body })
    } else {
      await api('/request-fields', { method: 'POST', body })
    }
    modal.value = false
    await load()
  } catch (err) {
    console.warn('[fields] save failed', err)
    formError.value = apiErrorMessage(err, 'Не удалось сохранить поле')
  } finally {
    saving.value = false
  }
}

async function remove(f: Field) {
  if (!confirm(`Удалить поле «${f.label}» (${f.code})?`)) return
  try {
    await api(`/request-fields/${f.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    console.warn('[fields] delete failed', err)
    alert(apiErrorMessage(err, 'Не удалось удалить поле'))
  }
}

await load().catch((err) => showLoadError(err, '[fields]'))
</script>
