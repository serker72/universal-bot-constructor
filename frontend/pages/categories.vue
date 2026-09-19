<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h1 class="page-title">Категории</h1>
      <button class="btn-primary" @click="openCreate">Добавить</button>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th>Название</th>
            <th class="w-24">Порядок</th>
            <th class="w-28">Активна</th>
            <th class="w-40">Действия</th>
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
            <td class="space-x-2 whitespace-nowrap">
              <button class="btn-secondary" @click="openEdit(cat)">Изменить</button>
              <button class="btn-secondary" @click="openManagers(cat)">Менеджеры</button>
              <button class="btn-danger" @click="remove(cat)">Удалить</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="4" class="py-6 text-center text-gray-400">Категорий пока нет</td>
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
  await loadManagers()
})

await load()
</script>
