// Nuxt: админ-панель (SPA, русский интерфейс, время Europe/Moscow)
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },

  // SPA: авторизация через httpOnly cookies + localStorage, SSR не нужен
  ssr: false,

  // Корень сайта → дашборд (middleware сам перенаправит на /login для гостей)
  routeRules: {
    '/': { redirect: { to: '/dashboard', statusCode: 302 } },
  },

  modules: ['@nuxtjs/tailwindcss'],

  // Глобальные стили (тема: кнопки, формы, таблицы, карточки)
  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      // База API backend (в prod проксируется nginx'ом, см. docker-compose.frontend.yml)
      backendUrl: process.env.NUXT_PUBLIC_BACKEND_URL || 'http://localhost:8000/api/v1',
    },
  },

  app: {
    head: {
      title: 'Конструктор меню бота',
      htmlAttrs: { lang: 'ru' },
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      // Шрифт Inter
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
        },
      ],
    },
  },
})
