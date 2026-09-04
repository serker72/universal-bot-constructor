<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 p-4">
    <!-- Декоративный фон -->
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-primary-600/30 blur-3xl" />
      <div class="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl" />
      <div class="absolute left-1/2 top-1/3 h-64 w-64 -translate-x-1/2 rounded-full bg-primary-500/10 blur-3xl" />
    </div>

    <!-- Карточка входа -->
    <div class="relative w-full max-w-md">
      <div class="rounded-2xl border border-white/10 bg-white/[0.06] p-8 shadow-2xl backdrop-blur-xl">
        <!-- Логотип -->
        <div class="mb-8 flex flex-col items-center text-center">
          <div class="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 shadow-lg shadow-primary-500/40">
            <AppIcon name="chat" class="h-7 w-7 text-white" />
          </div>
          <h1 class="text-xl font-semibold text-white">Конструктор меню бота</h1>
          <p class="mt-1 text-sm text-slate-400">Панель управления · вход</p>
        </div>

        <form class="space-y-4" @submit.prevent="submit">
          <div>
            <label class="mb-1.5 block text-sm font-medium text-slate-300" for="username">
              Имя пользователя
            </label>
            <input
              id="username"
              v-model="username"
              class="w-full rounded-lg border border-white/10 bg-white/[0.07] px-3.5 py-2.5 text-sm text-white placeholder:text-slate-500 transition focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
              type="text"
              required
              autocomplete="username"
              placeholder="admin"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-sm font-medium text-slate-300" for="password">
              Пароль
            </label>
            <input
              id="password"
              v-model="password"
              class="w-full rounded-lg border border-white/10 bg-white/[0.07] px-3.5 py-2.5 text-sm text-white placeholder:text-slate-500 transition focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
              type="password"
              required
              autocomplete="current-password"
              placeholder="••••••••"
            />
          </div>

          <p v-if="error" class="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300 ring-1 ring-inset ring-red-500/30">
            {{ error }}
          </p>

          <button
            class="w-full rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary-600/30 transition hover:from-primary-400 hover:to-primary-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/60 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            :disabled="loading"
          >
            {{ loading ? 'Вход…' : 'Войти' }}
          </button>
        </form>
      </div>

      <p class="mt-6 text-center text-xs text-slate-500">Universal Bot Constructor</p>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })

const auth = useAuth()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    await navigateTo('/dashboard')
  } catch (err) {
    const status = (err as { status?: number }).status
    if (status === 401) {
      error.value = 'Неверное имя пользователя или пароль'
    } else if (status === 429) {
      error.value = 'Слишком много попыток, попробуйте позже'
    } else {
      console.error('login failed:', err)
      error.value = 'Ошибка входа, попробуйте ещё раз'
    }
  } finally {
    loading.value = false
  }
}
</script>
