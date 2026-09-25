#!/bin/sh
# Периодическая перезагрузка nginx (prod): подхват сертификатов,
# продлённых certbot (certbot renew в соседнем контейнере).
# Запускается entrypoint'ом официального образа nginx
# (/docker-entrypoint.d/*.sh, файл должен быть исполняемым) до старта nginx;
# цикл уходит в фон, `nginx -s reload` — graceful (без обрыва соединений).
set -eu

DEFAULT_INTERVAL="6h"
INTERVAL="${NGINX_RELOAD_INTERVAL:-$DEFAULT_INTERVAL}"

# busybox sleep понимает только число с суффиксом s/m/h/d ("6hours" -> rc=1):
# с set -eu подоболочка завершилась бы молча и перезагрузки прекратились —
# проверяем формат при старте и откатываемся на значение по умолчанию
case "$INTERVAL" in
    ''|*[!0-9smhd]*|[smhd]*|*[smhd]*[0-9smhd]*)
        echo "40-reload-certs.sh: warn: invalid NGINX_RELOAD_INTERVAL='${INTERVAL}', using ${DEFAULT_INTERVAL}" >&2
        INTERVAL="$DEFAULT_INTERVAL"
        ;;
esac

(
    while :; do
        sleep "$INTERVAL" || sleep "$DEFAULT_INTERVAL" || true
        nginx -s reload 2>&1 | sed 's/^/40-reload-certs: /' || true
    done
) </dev/null &

echo "40-reload-certs.sh: info: nginx reload every ${INTERVAL}"
