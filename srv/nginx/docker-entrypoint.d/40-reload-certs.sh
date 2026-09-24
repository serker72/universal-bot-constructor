#!/bin/sh
# Периодическая перезагрузка nginx (prod): подхват сертификатов,
# продлённых certbot (certbot renew в соседнем контейнере).
# Запускается entrypoint'ом официального образа nginx
# (/docker-entrypoint.d/*.sh, файл должен быть исполняемым) до старта nginx;
# цикл уходит в фон, `nginx -s reload` — graceful (без обрыва соединений).
set -eu

INTERVAL="${NGINX_RELOAD_INTERVAL:-6h}"

(
    while :; do
        sleep "$INTERVAL"
        nginx -s reload 2>&1 | sed 's/^/40-reload-certs: /' || true
    done
) </dev/null &

echo "40-reload-certs.sh: info: nginx reload every ${INTERVAL}"
