<template>
  <UiModal :open="open" :title="title" @close="$emit('close')">
    <p v-if="hint" class="mb-3 text-sm text-gray-500">{{ hint }}</p>
    <p v-if="loading" class="mb-3 text-sm text-gray-500">Загрузка…</p>
    <p v-else-if="!managers.length" class="mb-3 text-sm text-gray-500">
      Нет активных пользователей с ролью «менеджер».
    </p>
    <div class="mb-4 max-h-64 space-y-2 overflow-y-auto">
      <label v-for="m in managers" :key="m.id" class="flex items-center gap-2 text-sm">
        <input v-model="selected" type="checkbox" :value="m.id" class="h-4 w-4" />
        {{ m.username }}
      </label>
    </div>
    <p v-if="error" class="mb-2 text-sm text-red-600">{{ error }}</p>
    <div class="flex justify-end gap-2">
      <button class="btn-secondary" type="button" @click="$emit('close')">Отмена</button>
      <button
        class="btn-primary"
        type="button"
        :disabled="saving || loading || !loaded"
        @click="save"
      >
        Сохранить
      </button>
    </div>
  </UiModal>
</template>

<script setup lang="ts">
// Модалка назначения менеджеров сущности (категории/объекта).
// endpoint — базовый путь сущности (/categories/5, /objects/12):
// GET/PUT {endpoint}/managers. До загрузки списка «Сохранить» недоступна,
// иначе PUT перезапишет доступы новой сущности списком предыдущей.
const props = defineProps<{
  open: boolean
  endpoint: string
  title: string
  hint?: string
}>()
const emit = defineEmits<{ close: [] }>()

const { api } = useApi()
const { managers, loadManagers } = useManagers()

const selected = ref<number[]>([])
const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)
const error = ref('')

// номер открытия: ответ устаревшего запроса не должен перезаписать выбор
let seq = 0

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    const current = ++seq
    const endpoint = props.endpoint
    selected.value = []
    loaded.value = false
    loading.value = true
    error.value = ''
    try {
      const [out] = await Promise.all([
        api<{ user_ids: number[] }>(`${endpoint}/managers`),
        loadManagers(true),
      ])
      // за время запроса модалку могли открыть для другой сущности
      if (current !== seq) return
      selected.value = [...out.user_ids]
      loaded.value = true
    } catch (err) {
      if (current !== seq) return
      console.warn('[managers-modal] load failed', err)
      error.value = apiErrorMessage(err, 'Не удалось загрузить менеджеров')
    } finally {
      if (current === seq) loading.value = false
    }
  },
)

async function save() {
  saving.value = true
  error.value = ''
  try {
    await api(`${props.endpoint}/managers`, {
      method: 'PUT',
      body: { user_ids: selected.value },
    })
    emit('close')
  } catch (err) {
    console.warn('[managers-modal] save failed', err)
    error.value = apiErrorMessage(err, 'Не удалось сохранить менеджеров')
  } finally {
    saving.value = false
  }
}
</script>
