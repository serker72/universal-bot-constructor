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
      // База API backend. По умолчанию — относительный путь (тот же origin за
      // nginx); для npm run dev без nginx задать NUXT_PUBLIC_BACKEND_URL,
      // например http://localhost:8000/api/v1
      backendUrl: process.env.NUXT_PUBLIC_BACKEND_URL || '/api/v1',
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
      // Внешние шрифты (Google Fonts) не подключаются: лишняя внешняя
      // зависимость и утечка IP администраторов третьей стороне (CSP: font-src 'self').
      // Inter используется, если установлен локально, иначе — системный sans-serif.
    },
  },
})
