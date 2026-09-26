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
              <UiBoolBadge :value="cat.is_active" />
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
      <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
    </div>

    <UiModal :open="modal" :title="form.id ? 'Изменить категорию' : 'Новая категория'" @close="modal = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label" for="cat-name">Название</label>
          <input id="cat-name" v-model="form.name" class="input" required maxlength="255" />
        </div>
        <div>
          <label class="label" for="cat-button-text">Текст для кнопки "Создать заявку"</label>
          <input
            id="cat-button-text"
            v-model="form.button_text"
            class="input"
            maxlength="64"
            placeholder="Создать заявку"
          />
          <p class="mt-1 text-xs text-gray-400">
            Текст кнопки на странице объекта в боте. Пусто — «Создать заявку».
          </p>
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
    <UiManagersModal
      :open="managersModal"
      :endpoint="`/categories/${managersCategoryId}`"
      title="Менеджеры категории"
      hint="Менеджеры категории получают доступ ко всем её объектам (заявки и уведомления)."
      @close="managersModal = false"
    />
    <!-- Состав полей заявки категории -->
    <UiModal :open="fieldsModal" title="Поля заявки категории" @close="fieldsModal = false">
      <p class="mb-3 text-sm text-gray-500">
        Поля формы заявки для объектов этой категории (порядок = порядок в диалоге бота).
      </p>
      <p v-if="fieldsLoading" class="mb-3 text-sm text-gray-500">Загрузка…</p>
      <p v-else-if="!fieldsAll.length" class="mb-3 text-sm text-gray-500">
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
        <button
          class="btn-primary"
          type="button"
          :disabled="fieldsSaving || fieldsLoading || !fieldsLoaded"
          @click="saveFields"
        >
          Сохранить
        </button>
      </div>
    </UiModal>
  </div>
</template>

<script setup lang="ts">
import type { Category, FieldDef } from '~/types/models'

const { api, page, pageAll } = useApi()
const isAdmin = useAuth().isAdmin

const limit = PAGE_SIZE
const { items, total, offset, load, changeOffset: goTo } = useListLoader<Category>(
  (off, signal) => page<Category>('/categories', { limit, offset: off }, signal),
  limit,
)
const modal = ref(false)
const saving = ref(false)
const formError = ref('')
const form = ref({ id: 0, name: '', button_text: '', sort_order: 0, is_active: true })

// модалка UiManagersModal: id категории нужен только для endpoint
const managersModal = ref(false)
const managersCategoryId = ref(0)

// -- поля заявки категории --------------------------------------------------
interface FieldRow {
  field: FieldDef
  selected: boolean
  sort_order: number
  is_required: boolean
}

const fieldsModal = ref(false)
const fieldsAll = ref<FieldDef[]>([])
const fieldsRows = ref<FieldRow[]>([])
const fieldsSaving = ref(false)
const fieldsError = ref('')
const fieldsCategoryId = ref(0)
const fieldsLoading = ref(false)
const fieldsLoaded = ref(false)

async function openFields(cat: Category) {
  // сброс состояния предыдущей категории: до загрузки «Сохранить» недоступна
  fieldsCategoryId.value = cat.id
  fieldsRows.value = []
  fieldsLoaded.value = false
  fieldsLoading.value = true
  fieldsError.value = ''
  fieldsModal.value = true
  try {
    // справочник перечитывается: поля могли измениться на странице «Поля заявки»
    fieldsAll.value = await pageAll<FieldDef>('/request-fields')
    const out = await api<{
      category_id: number
      fields: { field: FieldDef; sort_order: number; is_required: boolean }[]
    }>(`/request-fields/categories/${cat.id}/fields`)
    if (fieldsCategoryId.value !== cat.id) return
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
    fieldsLoaded.value = true
  } catch (err) {
    console.warn('[categories] fields load failed', err)
    fieldsError.value = apiErrorMessage(err, 'Не удалось загрузить поля')
  } finally {
    if (fieldsCategoryId.value === cat.id) fieldsLoading.value = false
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
    fieldsError.value = apiErrorMessage(err, 'Не удалось сохранить поля')
  } finally {
    fieldsSaving.value = false
  }
}

function changeOffset(v: number) {
  goTo(v, '[categories]')
}

function openCreate() {
  form.value = { id: 0, name: '', button_text: '', sort_order: items.value.length, is_active: true }
  formError.value = ''
  modal.value = true
}

function openEdit(cat: Category) {
  form.value = {
    id: cat.id,
    name: cat.name,
    button_text: cat.button_text ?? '',
    sort_order: cat.sort_order,
    is_active: cat.is_active,
  }
  formError.value = ''
  modal.value = true
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    const body = {
      name: form.value.name,
      // PATCH: null — не менять, "" — сброс на текст по умолчанию
      button_text: form.value.button_text.trim(),
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
    formError.value = apiErrorMessage(err, 'Не удалось сохранить категорию')
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
    alert(apiErrorMessage(err, 'Не удалось удалить категорию'))
  }
}

function openManagers(cat: Category) {
  managersCategoryId.value = cat.id
  managersModal.value = true
}

// ошибка загрузки — сообщение пользователю, а не пустая страница
await load().catch((err) => showLoadError(err, '[categories]'))
</script>
