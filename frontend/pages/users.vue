<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h1 class="page-title">Пользователи</h1>
      <button class="btn-primary" @click="openCreate">Добавить</button>
    </div>

    <div class="card overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr>
            <th>Имя входа</th>
            <th class="w-32">Роль</th>
            <th class="w-40">Telegram ID</th>
            <th class="w-28">Активен</th>
            <th class="w-44">Создан</th>
            <th class="w-44">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in items" :key="u.id">
            <td class="font-medium">{{ u.username }}</td>
            <td>{{ u.role === 'admin' ? 'Администратор' : 'Менеджер' }}</td>
            <td>{{ u.telegram_id ?? '—' }}</td>
            <td>
              <span :class="u.is_active ? 'text-green-600' : 'text-gray-400'">
                {{ u.is_active ? 'Да' : 'Нет' }}
              </span>
            </td>
            <td class="whitespace-nowrap">{{ formatDateTime(u.created_at) }}</td>
            <td class="space-x-2 whitespace-nowrap">
              <button class="btn-secondary" @click="openEdit(u)">Изменить</button>
              <button class="btn-danger" :disabled="u.id === auth.user.value?.id" @click="remove(u)">
                Удалить
              </button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="6" class="py-6 text-center text-gray-400">Пользователей нет</td>
          </tr>
        </tbody>
      </table>
      <div class="px-4 pb-4">
        <UiPagination :total="total" :limit="limit" :offset="offset" @change="changeOffset" />
      </div>
    </div>

    <UiModal :open="modal" :title="isEdit ? 'Изменить пользователя' : 'Новый пользователь'" @close="modal = false">
      <form class="space-y-4" @submit.prevent="save">
        <div v-if="!isEdit">
          <label class="label" for="u-username">Имя входа</label>
          <input id="u-username" v-model="form.username" class="input" required minlength="3" maxlength="255" />
        </div>
        <div>
          <label class="label" for="u-password">
            Пароль {{ isEdit ? '(оставьте пустым, чтобы не менять)' : '' }}
          </label>
          <input id="u-password" v-model="form.password" class="input" type="password" :required="!isEdit" minlength="8" maxlength="128" autocomplete="new-password" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label" for="u-role">Роль</label>
            <select id="u-role" v-model="form.role" class="input">
              <option value="manager">Менеджер</option>
              <option value="admin">Администратор</option>
            </select>
          </div>
          <div>
            <label class="label" for="u-tg">Telegram ID</label>
            <input id="u-tg" v-model="form.telegramId" class="input" type="number" placeholder="для уведомлений" />
          </div>
        </div>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="form.is_active" type="checkbox" class="h-4 w-4" />
          Активен
        </label>
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
interface User {
  id: number
  username: string
  role: 'admin' | 'manager'
  telegram_id: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

const auth = useAuth()
const { api, page } = useApi()

const items = ref<User[]>([])
const total = ref(0)
const limit = PAGE_SIZE
const offset = ref(0)
const modal = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formError = ref('')
const form = ref({ id: 0, username: '', password: '', role: 'manager' as 'admin' | 'manager', telegramId: '', is_active: true })

async function load() {
  const p = await page<User>('/users', { limit, offset: offset.value })
  items.value = p.items
  total.value = p.total
}

function changeOffset(v: number) {
  offset.value = v
  load()
}

function openCreate() {
  isEdit.value = false
  form.value = { id: 0, username: '', password: '', role: 'manager', telegramId: '', is_active: true }
  formError.value = ''
  modal.value = true
}

function openEdit(u: User) {
  isEdit.value = true
  form.value = {
    id: u.id,
    username: u.username,
    password: '',
    role: u.role,
    telegramId: u.telegram_id === null ? '' : String(u.telegram_id),
    is_active: u.is_active,
  }
  formError.value = ''
  modal.value = true
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    if (isEdit.value) {
      const body: Record<string, unknown> = {
        role: form.value.role,
        telegram_id: form.value.telegramId ? Number(form.value.telegramId) : null,
        is_active: form.value.is_active,
      }
      if (form.value.password) body.password = form.value.password
      await api(`/users/${form.value.id}`, { method: 'PATCH', body })
    } else {
      await api('/users', {
        method: 'POST',
        body: {
          username: form.value.username,
          password: form.value.password,
          role: form.value.role,
          telegram_id: form.value.telegramId ? Number(form.value.telegramId) : null,
          is_active: form.value.is_active,
        },
      })
    }
    modal.value = false
    await load()
  } catch {
    formError.value = 'Не удалось сохранить пользователя (имя занято? пароль от 8 символов?)'
  } finally {
    saving.value = false
  }
}

async function remove(u: User) {
  if (!confirm(`Удалить пользователя «${u.username}»?`)) return
  try {
    await api(`/users/${u.id}`, { method: 'DELETE' })
    await load()
  } catch {
    alert('Не удалось удалить пользователя')
  }
}

await load()
</script>
