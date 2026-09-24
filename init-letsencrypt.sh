#!/bin/bash
# Первичный выпуск сертификата Let's Encrypt (prod, webroot HTTP-01).
#
# Проблема «курицы и яйца»: nginx (prod) не стартует без файлов сертификата,
# а certbot не пройдёт HTTP-01 без работающего nginx. Порядок:
#   1) временный самоподписанный сертификат -> nginx стартует;
#   2) временный сертификат удаляется, certbot выпускает настоящий (webroot);
#   3) nginx -s reload, запуск certbot (цикл продления).
#
# Параметры — из .env (PROJECT_ENVIRONMENT=prod, PROJECT_DOMAIN, CERTBOT_EMAIL,
# CERTBOT_DATA_DIR) через docker compose; каталоги ${CERTBOT_DATA_DIR}/{conf,www}
# должны существовать.
#
# Использование (из корня проекта):
#   ./init-letsencrypt.sh             # выпуск (если настоящего сертификата ещё нет)
#   ./init-letsencrypt.sh --staging   # тестовый CA Let's Encrypt (без лимитов)
#   ./init-letsencrypt.sh --force     # перевыпуск при наличии сертификата
set -euo pipefail

scriptDir=$(dirname -- "$(readlink -f -- "$0")")
cd "$scriptDir"

STAGING=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --staging) STAGING=1 ;;
        --force) FORCE=1 ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        *) echo "Неизвестный аргумент: $arg" >&2; exit 2 ;;
    esac
done

compose() { docker compose "$@"; }
# Команда в контейнере certbot (переменные PROJECT_DOMAIN/CERTBOT_EMAIL — из environment)
certbot_sh() { compose run --rm --no-deps --entrypoint sh certbot -c "$1"; }

# --- проверки окружения ---
if ! compose config --services | grep -qx certbot; then
    echo "Сервис certbot не найден: нужен PROJECT_ENVIRONMENT=prod в .env" >&2
    exit 1
fi

certbot_sh '
    [ -n "$PROJECT_DOMAIN" ] || { echo "PROJECT_DOMAIN не задан" >&2; exit 1; }
    case "$CERTBOT_EMAIL" in
        ""|change_me) echo "CERTBOT_EMAIL не задан (change_me) в .env" >&2; exit 1 ;;
    esac
'

# Настоящий сертификат уже есть (у временного нет renewal-конфига)
if [ "$FORCE" -eq 0 ] && certbot_sh 'test -f "/etc/letsencrypt/renewal/$PROJECT_DOMAIN.conf"'; then
    echo "Сертификат уже выпущен (перевыпуск: --force). Продление — сервис certbot."
    exit 0
fi

# --- 1. временный сертификат ---
echo "### Временный самоподписанный сертификат"
certbot_sh '
    live="/etc/letsencrypt/live/$PROJECT_DOMAIN"
    if [ ! -f "/etc/letsencrypt/renewal/$PROJECT_DOMAIN.conf" ]; then
        mkdir -p "$live"
        openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
            -keyout "$live/privkey.pem" -out "$live/fullchain.pem" \
            -subj "/CN=localhost" 2>/dev/null
    fi
'

echo "### Запуск nginx"
compose up -d nginx
compose exec nginx nginx -t

# --- 2. выпуск настоящего сертификата ---
echo "### Удаление временного сертификата"
certbot_sh '
    if [ ! -f "/etc/letsencrypt/renewal/$PROJECT_DOMAIN.conf" ]; then
        rm -rf "/etc/letsencrypt/live/$PROJECT_DOMAIN" \
               "/etc/letsencrypt/archive/$PROJECT_DOMAIN"
    fi
'

echo "### Выпуск сертификата Let's Encrypt"
staging_arg=""
[ "$STAGING" -eq 1 ] && staging_arg="--staging"
force_arg=""
[ "$FORCE" -eq 1 ] && force_arg="--force-renewal"
certbot_sh "certbot certonly --webroot -w /var/www/certbot \
    -d \"\$PROJECT_DOMAIN\" --email \"\$CERTBOT_EMAIL\" \
    --agree-tos --no-eff-email --non-interactive $staging_arg $force_arg"

# --- 3. применение ---
echo "### Перезагрузка nginx и запуск certbot (продление)"
compose exec nginx nginx -s reload
compose up -d certbot

echo "Готово: https://$(certbot_sh 'printf %s "$PROJECT_DOMAIN"')"
