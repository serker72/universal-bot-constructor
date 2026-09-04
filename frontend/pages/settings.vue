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
const form = ref({ page_size: '10', cancel_hours: '24', welcome_text: '', consent_text: '' })

const KEY_PAGE = 'bot.page_size'
const KEY_CANCEL = 'requests.cancel_interval_hours'
const KEY_WELCOME = 'bot.welcome_text'
const KEY_CONSENT = 'bot.consent_text'

function apply(settings: Record<string, string>) {
  form.value = {
    page_size: settings[KEY_PAGE] ?? '10',
    cancel_hours: settings[KEY_CANCEL] ?? '24',
    welcome_text: settings[KEY_WELCOME] ?? '',
    consent_text: settings[KEY_CONSENT] ?? '',
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
