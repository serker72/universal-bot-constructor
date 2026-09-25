#!/bin/sh
# Запуск redis-server с паролем из окружения (REDIS_PASSWORD), а не из argv:
# --requirepass в command виден в `ps` и `docker inspect`. Конфиг пишется
# во временный файл внутри контейнера; пароль экранируется (\ и ").
set -eu

: "${REDIS_PASSWORD:?REDIS_PASSWORD is required}"
REDIS_PORT="${REDIS_PORT:-6379}"

escaped=$(printf '%s' "$REDIS_PASSWORD" | sed 's/[\\"]/\\&/g')
umask 077
printf 'port %s\nappendonly yes\nrequirepass "%s"\n' "$REDIS_PORT" "$escaped" > /tmp/redis.conf

exec redis-server /tmp/redis.conf
