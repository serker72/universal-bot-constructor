<template>
  <div class="max-w-2xl">
    <h1 class="page-title mb-4">Настройки</h1>

    <div v-if="loadError" class="card p-6 text-red-600">Не удалось загрузить настройки</div>

    <form v-else class="card space-y-5 p-6" @submit.prevent="save">
      <div>
        <label class="label" for="st-page">Размер страницы меню бота</label>
        <input id="st-page" v-model="form.page_size" class="input" type="number" min="1" max="50" />
      </div>
      <div>
        <label class="label" for="st-cancel">
          Интервал отмены подтверждённой заявки, часов
        </label>
        <input id="st-cancel" v-model="form.cancel_hours" class="input" type="number" min="0" max="720" />
      </div>
      <div>
        <label class="label" for="st-welcome">Текст приветствия бота</label>
        <textarea id="st-welcome" v-model="form.welcome_text" class="input min-h-20"></textarea>
      </div>
      <div>
        <label class="label" for="st-consent">Текст согласия на обработку персональных данных</label>
        <textarea id="st-consent" v-model="form.consent_text" class="input min-h-24"></textarea>
      </div>
      <div class="flex items-center gap-2">
        <input id="st-use-time" v-model="form.use_time" class="checkbox" type="checkbox" />
        <label class="label" for="st-use-time">Использовать время в заявке (выбор часов и минут)</label>
      </div>
      <div class="flex items-center gap-2">
        <input id="st-use-end-date" v-model="form.use_end_date" class="checkbox" type="checkbox" />
        <label class="label" for="st-use-end-date">Использовать дату окончания в заявке</label>
      </div>

      <p v-if="message" :class="saved ? 'text-green-600' : 'text-red-600'" class="text-sm">
        {{ message }}
      </p>
      <button class="btn-primary" type="submit" :disabled="saving">Сохранить</button>
    </form>
  </div>
</template>

<script setup lang="ts">
const { api } = useApi()

const loadError = ref(false)
const saving = ref(false)
const saved = ref(false)
const message = ref('')
const form = ref({
  page_size: '10',
  cancel_hours: '24',
  welcome_text: '',
  consent_text: '',
  use_time: false,
  use_end_date: false,
})

const KEY_PAGE = 'bot.page_size'
const KEY_CANCEL = 'requests.cancel_interval_hours'
const KEY_WELCOME = 'bot.welcome_text'
const KEY_CONSENT = 'bot.consent_text'
const KEY_USE_TIME = 'requests.is_use_time_in_request'
const KEY_USE_END_DATE = 'requests.is_use_end_date_in_request'

function apply(settings: Record<string, string>) {
  form.value = {
    page_size: settings[KEY_PAGE] ?? '10',
    cancel_hours: settings[KEY_CANCEL] ?? '24',
    welcome_text: settings[KEY_WELCOME] ?? '',
    consent_text: settings[KEY_CONSENT] ?? '',
    use_time: (settings[KEY_USE_TIME] ?? 'false').toLowerCase() === 'true',
    use_end_date: (settings[KEY_USE_END_DATE] ?? 'false').toLowerCase() === 'true',
  }
}

async function save() {
  saving.value = true
  message.value = ''
  try {
    const out = await api<{ settings: Record<string, string> }>('/settings', {
      method: 'PUT',
      body: {
        settings: {
          [KEY_PAGE]: form.value.page_size,
          [KEY_CANCEL]: form.value.cancel_hours,
          [KEY_WELCOME]: form.value.welcome_text,
          [KEY_CONSENT]: form.value.consent_text,
          [KEY_USE_TIME]: String(form.value.use_time),
          [KEY_USE_END_DATE]: String(form.value.use_end_date),
        },
      },
    })
    apply(out.settings)
    saved.value = true
    message.value = 'Настройки сохранены'
  } catch {
    saved.value = false
    message.value = 'Не удалось сохранить настройки'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const out = await api<{ settings: Record<string, string> }>('/settings')
    apply(out.settings)
  } catch {
    loadError.value = true
  }
})
</script>
