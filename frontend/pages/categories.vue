<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h1 class="page-title">Категории</h1>
      <button v-if="isAdmin" class="btn-primary" @click="openCreate">Добавить</button>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th>Название</th>
            <th class="w-24">Порядок</th>
            <th class="w-28">Активна</th>
            <th v-if="isAdmin" class="w-40">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="cat in items" :key="cat.id">
            <td class="font-medium">{{ cat.name }}</td>
            <td>{{ cat.sort_order }}</td>
            <td>
              <span :class="cat.is_active ? 'text-green-600' : 'text-gray-400'">
                {{ cat.is_active ? 'Да' : 'Нет' }}
              </span>
            </td>
            <td v-if="isAdmin" class="space-x-2 whitespace-nowrap">
              <button class="btn-secondary" @click="openEdit(cat)">Изменить</button>
              <button class="btn-secondary" @click="openManagers(cat)">Менеджеры</button>
              <button class="btn-secondary" @click="openFields(cat)">Поля заявки</button>
              <button class="btn-danger" @click="remove(cat)">Удалить</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td :colspan="isAdmin ? 4 : 3" class="py-6 text-center text-gray-400">Категорий пока нет</td>
          </tr>
        </tbody>
      </table>
      <div class="px-4 pb-4">
        <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
      </div>
    </div>

    <UiModal :open="modal" :title="form.id ? 'Изменить категорию' : 'Новая категория'" @close="modal = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label" for="cat-name">Название</label>
          <input id="cat-name" v-model="form.name" class="input" required maxlength="255" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label" for="cat-sort">Порядок</label>
            <input id="cat-sort" v-model.number="form.sort_order" class="input" type="number" />
          </div>
          <label class="mt-6 flex items-center gap-2 text-sm">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4" />
            Активна
          </label>
        </div>
        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" type="button" @click="modal = false">Отмена</button>
          <button class="btn-primary" type="submit" :disabled="saving">Сохранить</button>
        </div>
      </form>
    </UiModal>

    <!-- Назначение менеджеров категории -->
    <UiModal :open="managersModal" title="Менеджеры категории" @close="managersModal = false">
      <p class="mb-3 text-sm text-gray-500">
        Менеджеры категории получают доступ ко всем её объектам (заявки и уведомления).
      </p>
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
    <!-- Состав полей заявки категории -->
    <UiModal :open="fieldsModal" title="Поля заявки категории" @close="fieldsModal = false">
      <p class="mb-3 text-sm text-gray-500">
        Поля формы заявки для объектов этой категории (порядок = порядок в диалоге бота).
      </p>
      <p v-if="!fieldsAll.length" class="mb-3 text-sm text-gray-500">
        Справочник полей пуст — добавьте поля на странице «Поля заявки».
      </p>
      <div class="mb-4 max-h-80 space-y-2 overflow-y-auto">
        <div
          v-for="(row, i) in fieldsRows"
          :key="row.field.id"
          class="flex items-center gap-2 text-sm"
        >
          <input
            :checked="row.selected"
            type="checkbox"
            class="h-4 w-4"
            @change="row.selected = !row.selected"
          />
          <span class="w-6 text-gray-400">{{ i + 1 }}.</span>
          <span class="flex-1">{{ row.field.label }} ({{ row.field.code }})</span>
          <input
            v-model.number="row.sort_order"
            class="input w-20"
            type="number"
            min="0"
            placeholder="№"
          />
          <label class="flex items-center gap-1 text-xs text-gray-500">
            <input v-model="row.is_required" type="checkbox" class="h-4 w-4" />
            обяз.
          </label>
        </div>
      </div>
      <p v-if="fieldsError" class="mb-2 text-sm text-red-600">{{ fieldsError }}</p>
      <div class="flex justify-end gap-2">
        <button class="btn-secondary" type="button" @click="fieldsModal = false">Отмена</button>
        <button class="btn-primary" type="button" :disabled="fieldsSaving" @click="saveFields">
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
  sort_order: number
  is_active: boolean
}

const { api, page } = useApi()
const { managers, loadManagers } = useManagers()
const isAdmin = useAuth().isAdmin

const items = ref<Category[]>([])
const total = ref(0)
const limit = PAGE_SIZE
const offset = ref(0)
const modal = ref(false)
const saving = ref(false)
const formError = ref('')
const form = ref({ id: 0, name: '', sort_order: 0, is_active: true })

const managersModal = ref(false)
const selectedManagers = ref<number[]>([])
const managersSaving = ref(false)
const managersError = ref('')
const managersCategoryId = ref(0)

// -- поля заявки категории --------------------------------------------------
interface ReqField {
  id: number
  code: string
  type: string
  label: string
  is_required_default: boolean
  meta_data: Record<string, unknown> | null
}
interface FieldRow {
  field: ReqField
  selected: boolean
  sort_order: number
  is_required: boolean
}

const fieldsModal = ref(false)
const fieldsAll = ref<ReqField[]>([])
const fieldsRows = ref<FieldRow[]>([])
const fieldsSaving = ref(false)
const fieldsError = ref('')
const fieldsCategoryId = ref(0)

async function openFields(cat: Category) {
  fieldsCategoryId.value = cat.id
  fieldsError.value = ''
  fieldsModal.value = true
  try {
    if (!fieldsAll.value.length) {
      const p = await page<ReqField>('/request-fields', { limit: 1000 })
      fieldsAll.value = p.items
    }
    const out = await api<{
      category_id: number
      fields: { field: ReqField; sort_order: number; is_required: boolean }[]
    }>(`/request-fields/categories/${cat.id}/fields`)
    const linked = new Map(out.fields.map((f) => [f.field.id, f]))
    fieldsRows.value = fieldsAll.value.map((f) => {
      const link = linked.get(f.id)
      return {
        field: f,
        selected: link !== undefined,
        sort_order: link?.sort_order ?? 0,
        is_required: link?.is_required ?? f.is_required_default,
      }
    })
  } catch (err) {
    console.warn('[categories] fields load failed', err)
    fieldsError.value = 'Не удалось загрузить поля'
  }
}

async function saveFields() {
  fieldsSaving.value = true
  fieldsError.value = ''
  try {
    const fields = fieldsRows.value
      .filter((r) => r.selected)
      .map((r) => ({
        field_id: r.field.id,
        sort_order: r.sort_order,
        is_required: r.is_required,
      }))
    await api(`/request-fields/categories/${fieldsCategoryId.value}/fields`, {
      method: 'PUT',
      body: { fields },
    })
    fieldsModal.value = false
  } catch (err) {
    console.warn('[categories] fields save failed', err)
    fieldsError.value = 'Не удалось сохранить поля'
  } finally {
    fieldsSaving.value = false
  }
}

async function load() {
  const p = await page<Category>('/categories', { limit, offset: offset.value })
  items.value = p.items
  total.value = p.total
}

function changeOffset(v: number) {
  offset.value = v
  load()
}

function openCreate() {
  form.value = { id: 0, name: '', sort_order: items.value.length, is_active: true }
  formError.value = ''
  modal.value = true
}

function openEdit(cat: Category) {
  form.value = { id: cat.id, name: cat.name, sort_order: cat.sort_order, is_active: cat.is_active }
  formError.value = ''
  modal.value = true
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    const body = {
      name: form.value.name,
      sort_order: form.value.sort_order,
      is_active: form.value.is_active,
    }
    if (form.value.id) {
      await api(`/categories/${form.value.id}`, { method: 'PATCH', body })
    } else {
      await api('/categories', { method: 'POST', body })
    }
    modal.value = false
    await load()
  } catch (err) {
    console.warn('[categories] save failed', err)
    formError.value = 'Не удалось сохранить категорию'
  } finally {
    saving.value = false
  }
}

async function remove(cat: Category) {
  if (!confirm(`Удалить категорию «${cat.name}»? Объекты категории будут удалены.`)) return
  try {
    await api(`/categories/${cat.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    console.warn('[categories] delete failed', err)
    alert('Не удалось удалить категорию')
  }
}

async function openManagers(cat: Category) {
  managersCategoryId.value = cat.id
  managersError.value = ''
  managersModal.value = true
  try {
    const out = await api<{ category_id: number; user_ids: number[] }>(`/categories/${cat.id}/managers`)
    selectedManagers.value = [...out.user_ids]
  } catch (err) {
    console.warn('[categories] managers load failed', err)
    managersError.value = 'Не удалось загрузить менеджеров'
  }
}

async function saveManagers() {
  managersSaving.value = true
  managersError.value = ''
  try {
    await api(`/categories/${managersCategoryId.value}/managers`, {
      method: 'PUT',
      body: { user_ids: selectedManagers.value },
    })
    managersModal.value = false
  } catch (err) {
    console.warn('[categories] managers save failed', err)
    managersError.value = 'Не удалось сохранить менеджеров'
  } finally {
    managersSaving.value = false
  }
}

onMounted(async () => {
  // список менеджеров нужен только для admin-модалок назначения
  if (isAdmin.value) await loadManagers()
})

await load()
</script>
