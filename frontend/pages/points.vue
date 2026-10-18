<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h1 class="page-title">Точки продаж</h1>
      <button class="btn-primary" @click="openCreate">Добавить</button>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th>Название</th>
            <th>Адрес</th>
            <th class="w-32">Часовой пояс</th>
            <th class="w-32">График</th>
            <th class="w-24">Активна</th>
            <th class="w-64">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="point in items" :key="point.id">
            <td class="font-medium">{{ point.name }}</td>
            <td>{{ point.address }}</td>
            <td>{{ point.timezone }}</td>
            <td>{{ point.work_interval_begin.slice(0, 5) }}–{{ point.work_interval_end.slice(0, 5) }}</td>
            <td>
              <UiBoolBadge :value="point.is_active" />
            </td>
            <td class="space-x-2 whitespace-nowrap">
              <button class="btn-secondary" @click="openEdit(point)">Изменить</button>
              <button class="btn-secondary" @click="openCategories(point)">Категории</button>
              <button class="btn-secondary" @click="openObjects(point)">Объекты</button>
              <button class="btn-secondary" @click="copyLink(point)">ТГ бот</button>
              <button class="btn-danger" @click="remove(point)">Удалить</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="py-6 text-center text-gray-400">Точек пока нет</td>
          </tr>
        </tbody>
      </table>
      <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
    </div>

    <!-- Создание/редактирование -->
    <UiModal :open="modal" :title="form.id ? 'Изменить точку' : 'Новая точка'" @close="modal = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label" for="pt-name">Название</label>
          <input id="pt-name" v-model="form.name" class="input" required maxlength="128" />
        </div>
        <div>
          <label class="label" for="pt-address">Адрес</label>
          <input id="pt-address" v-model="form.address" class="input" required maxlength="255" />
        </div>
        <div>
          <label class="label" for="pt-timezone">Часовой пояс (IANA)</label>
          <input id="pt-timezone" v-model="form.timezone" class="input" required maxlength="64" placeholder="Europe/Moscow" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label" for="pt-begin">Начало графика</label>
            <input id="pt-begin" v-model="form.work_interval_begin" class="input" type="time" required />
          </div>
          <div>
            <label class="label" for="pt-end">Окончание графика</label>
            <input id="pt-end" v-model="form.work_interval_end" class="input" type="time" required />
          </div>
        </div>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="form.is_active" type="checkbox" class="h-4 w-4" />
          Активна
        </label>
        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" type="button" @click="modal = false">Отмена</button>
          <button class="btn-primary" type="submit" :disabled="saving">Сохранить</button>
        </div>
      </form>
    </UiModal>

    <!-- Привязка категорий -->
    <UiModal :open="catModal" :title="`Категории точки: ${modalPointName}`" @close="catModal = false">
      <p class="mb-3 text-sm text-gray-500">
        Категория видна точке, если привязана к ней ИЛИ не привязана ни к одной (глобальная).
      </p>
      <p v-if="catLoading" class="mb-3 text-sm text-gray-500">Загрузка…</p>
      <p v-else-if="!catAll.length" class="mb-3 text-sm text-gray-500">
        Категорий нет — создайте их на странице «Категории».
      </p>
      <div class="mb-4 max-h-80 space-y-2 overflow-y-auto">
        <label v-for="c in catAll" :key="c.id" class="flex items-center gap-2 text-sm">
          <input v-model="catSelected" type="checkbox" :value="c.id" class="h-4 w-4" />
          {{ c.name }}
          <span v-if="c.is_global" class="text-xs text-gray-400">🌍 глобальная</span>
        </label>
      </div>
      <p v-if="catError" class="mb-2 text-sm text-red-600">{{ catError }}</p>
      <div class="flex justify-end gap-2">
        <button class="btn-secondary" type="button" @click="catModal = false">Отмена</button>
        <button class="btn-primary" type="button" :disabled="catSaving || catLoading || !catLoaded" @click="saveCategories">
          Сохранить
        </button>
      </div>
    </UiModal>

    <!-- Привязка объектов -->
    <UiModal :open="objModal" :title="`Объекты точки: ${modalPointName}`" @close="objModal = false">
      <p class="mb-3 text-sm text-gray-500">
        Объект виден точке, если привязан к ней ИЛИ не привязан ни к одному (глобальный).
      </p>
      <p v-if="objLoading" class="mb-3 text-sm text-gray-500">Загрузка…</p>
      <p v-else-if="!objAll.length" class="mb-3 text-sm text-gray-500">
        Объектов нет — создайте их на странице «Объекты».
      </p>
      <div class="mb-4 max-h-80 space-y-2 overflow-y-auto">
        <label v-for="o in objAll" :key="o.id" class="flex items-center gap-2 text-sm">
          <input v-model="objSelected" type="checkbox" :value="o.id" class="h-4 w-4" />
          {{ o.name }}
          <span v-if="o.is_global" class="text-xs text-gray-400">🌍 глобальный</span>
        </label>
      </div>
      <p v-if="objError" class="mb-2 text-sm text-red-600">{{ objError }}</p>
      <div class="flex justify-end gap-2">
        <button class="btn-secondary" type="button" @click="objModal = false">Отмена</button>
        <button class="btn-primary" type="button" :disabled="objSaving || objLoading || !objLoaded" @click="saveObjects">
          Сохранить
        </button>
      </div>
    </UiModal>
  </div>
</template>

<script setup lang="ts">
import type { Category, Obj, Point } from '~/types/models'

const { api, page, pageAll } = useApi()

const limit = PAGE_SIZE
const { items, total, offset, load, changeOffset: goTo } = useListLoader<Point>(
  (off, signal) => page<Point>('/points', { limit, offset: off }, signal),
  limit,
)

// username бота — для deep-link «выбрать филиал» (bot.username в настройках)
const botUsername = ref('')

function changeOffset(v: number) {
  goTo(v, '[points]')
}

// -- форма CRUD --------------------------------------------------------------

const modal = ref(false)
const saving = ref(false)
const formError = ref('')
const form = ref({
  id: 0,
  name: '',
  address: '',
  timezone: 'Europe/Moscow',
  work_interval_begin: '09:00',
  work_interval_end: '19:00',
  is_active: true,
})

function openCreate() {
  form.value = {
    id: 0,
    name: '',
    address: '',
    timezone: 'Europe/Moscow',
    work_interval_begin: '09:00',
    work_interval_end: '19:00',
    is_active: true,
  }
  formError.value = ''
  modal.value = true
}

function openEdit(p: Point) {
  form.value = {
    id: p.id,
    name: p.name,
    address: p.address,
    timezone: p.timezone,
    work_interval_begin: p.work_interval_begin.slice(0, 5),
    work_interval_end: p.work_interval_end.slice(0, 5),
    is_active: p.is_active,
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
      address: form.value.address,
      timezone: form.value.timezone,
      work_interval_begin: form.value.work_interval_begin,
      work_interval_end: form.value.work_interval_end,
      is_active: form.value.is_active,
    }
    if (form.value.id) {
      await api(`/points/${form.value.id}`, { method: 'PATCH', body })
    } else {
      await api('/points', { method: 'POST', body })
    }
    modal.value = false
    await load()
  } catch (err) {
    console.warn('[points] save failed', err)
    formError.value = apiErrorMessage(err, 'Не удалось сохранить точку')
  } finally {
    saving.value = false
  }
}

async function remove(p: Point) {
  if (!confirm(`Удалить точку «${p.name}»? Посетители потеряют привязку к ней.`)) return
  try {
    await api(`/points/${p.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    console.warn('[points] delete failed', err)
    alert(apiErrorMessage(err, 'Не удалось удалить точку'))
  }
}

// -- deep-link копирование ----------------------------------------------------

/** Ссылка «выбрать филиал»: https://t.me/<username>?start=point_{id} */
function pointLink(p: Point): string {
  return `https://t.me/${botUsername.value}?start=point_${p.id}`
}

async function copyLink(p: Point) {
  if (!botUsername.value) {
    alert('Имя бота не задано — заполните его на странице «Настройки».')
    return
  }
  const link = pointLink(p)
  try {
    await navigator.clipboard.writeText(link)
    alert(`Ссылка скопирована:\n${link}`)
  } catch {
    // clipboard недоступен (http-контекст) — показать для ручного копирования
    alert(`Скопируйте вручную:\n${link}`)
  }
}

// -- привязки категорий/объектов ----------------------------------------------

const catModal = ref(false)
const objModal = ref(false)
const modalPointId = ref(0)
const modalPointName = ref('')

const catAll = ref<Category[]>([])
const catSelected = ref<number[]>([])
const catLoading = ref(false)
const catLoaded = ref(false)
const catSaving = ref(false)
const catError = ref('')

const objAll = ref<Obj[]>([])
const objSelected = ref<number[]>([])
const objLoading = ref(false)
const objLoaded = ref(false)
const objSaving = ref(false)
const objError = ref('')

async function openCategories(p: Point) {
  modalPointId.value = p.id
  modalPointName.value = p.name
  catSelected.value = []
  catLoaded.value = false
  catLoading.value = true
  catError.value = ''
  catModal.value = true
  try {
    // справочники перечитываются: категории/объекты могли измениться
    // на своих страницах
    const [all, out] = await Promise.all([
      pageAll<Category>('/categories'),
      api<{ category_ids: number[] }>(`/points/${p.id}/categories`),
    ])
    catAll.value = all
    catSelected.value = [...out.category_ids]
    catLoaded.value = true
  } catch (err) {
    console.warn('[points] categories load failed', err)
    catError.value = apiErrorMessage(err, 'Не удалось загрузить категории')
  } finally {
    catLoading.value = false
  }
}

async function saveCategories() {
  catSaving.value = true
  catError.value = ''
  try {
    await api(`/points/${modalPointId.value}/categories`, {
      method: 'PUT',
      body: { category_ids: catSelected.value },
    })
    catModal.value = false
  } catch (err) {
    console.warn('[points] categories save failed', err)
    catError.value = apiErrorMessage(err, 'Не удалось сохранить категории')
  } finally {
    catSaving.value = false
  }
}

async function openObjects(p: Point) {
  modalPointId.value = p.id
  modalPointName.value = p.name
  objSelected.value = []
  objLoaded.value = false
  objLoading.value = true
  objError.value = ''
  objModal.value = true
  try {
    // справочники перечитываются: категории/объекты могли измениться
    // на своих страницах
    const [all, out] = await Promise.all([
      pageAll<Obj>('/objects'),
      api<{ object_ids: number[] }>(`/points/${p.id}/objects`),
    ])
    objAll.value = all
    objSelected.value = [...out.object_ids]
    objLoaded.value = true
  } catch (err) {
    console.warn('[points] objects load failed', err)
    objError.value = apiErrorMessage(err, 'Не удалось загрузить объекты')
  } finally {
    objLoading.value = false
  }
}

async function saveObjects() {
  objSaving.value = true
  objError.value = ''
  try {
    await api(`/points/${modalPointId.value}/objects`, {
      method: 'PUT',
      body: { object_ids: objSelected.value },
    })
    objModal.value = false
  } catch (err) {
    console.warn('[points] objects save failed', err)
    objError.value = apiErrorMessage(err, 'Не удалось сохранить объекты')
  } finally {
    objSaving.value = false
  }
}

// ошибка загрузки — сообщение пользователю, а не пустая страница
await load().catch((err) => showLoadError(err, '[points]'))

// username бота нужен для кнопки «Ссылка»: без него deep-link не собрать
try {
  const out = await api<{ settings: Record<string, string> }>('/settings')
  botUsername.value = out.settings['bot.username'] ?? ''
} catch (err) {
  console.warn('[points] bot username load failed', err)
}
</script>
