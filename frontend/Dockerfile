# Frontend (Nuxt.js): сборка и запуск node .output/server/index.mjs
# Использование: docker compose -f docker-compose.frontend.yml up -d --build
# Версия node совпадает с локальным хостом: frontend/.nvmrc = 24.12
# (хост nvm: v24.12.0) — менять обе одновременно

FROM node:24.12-alpine AS build
WORKDIR /app

# lock-файл обязателен: npm ci ставит ровно зафиксированные версии и падает
# при рассинхроне package.json/package-lock.json (без fallback на npm install)
COPY package.json package-lock.json ./
RUN npm ci

# node_modules хоста исключены .dockerignore
COPY . .
RUN npm run build

FROM node:24.12-alpine
WORKDIR /app

ENV NODE_ENV=production
COPY --from=build --chown=node:node /app/.output ./.output

# непривилегированный пользователь образа node
USER node

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
