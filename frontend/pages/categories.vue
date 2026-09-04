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

const items = ref<Category[]>([])
const total = ref(0)
const limit = PAGE_SIZE
const offset = ref(0)
const modal = ref(false)
const saving = ref(false)
const formError = ref('')
const form = ref({ id: 0, name: '', sort_order: 0, is_active: true })

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
  } catch {
    alert('Не удалось удалить категорию')
  }
}

await load()
</script>
