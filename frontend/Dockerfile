# Frontend (Nuxt.js): сборка и запуск node .output/server/index.mjs
# Использование: docker compose -f docker-compose.frontend.yml up -d --build

FROM node:22-alpine AS build
WORKDIR /app

COPY package.json ./
COPY package-lock.json* ./
RUN npm ci || npm install

COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app

ENV NODE_ENV=production
COPY --from=build /app/.output ./.output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
