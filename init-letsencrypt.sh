#!/bin/bash
# Первичный выпуск сертификата Let's Encrypt (prod, webroot HTTP-01).
#
# Проблема «курицы и яйца»: nginx (prod) не стартует без файлов сертификата,
# а certbot не пройдёт HTTP-01 без работающего nginx. Порядок:
#   1) временный самоподписанный сертификат -> nginx стартует;
#   2) временный сертификат удаляется, certbot выпускает настоящий (webroot);
#   3) nginx -s reload, запуск certbot (цикл продления).
# Перед удалением текущий сертификат (временный или staging) копируется в
# /etc/letsencrypt/.ubc-backup; при сбое выпуска он восстанавливается — nginx
# не уходит в restart-loop «cannot load certificate» после рестарта.
#
# Параметры — из .env (PROJECT_ENVIRONMENT=prod, PROJECT_DOMAIN, CERTBOT_EMAIL,
# CERTBOT_DATA_DIR) через docker compose; каталоги ${CERTBOT_DATA_DIR}/{conf,www}
# должны существовать.
#
# Использование (из корня проекта):
#   ./init-letsencrypt.sh --staging   # сначала — тестовый CA Let's Encrypt (без лимитов)
#   ./init-letsencrypt.sh             # боевой сертификат (staging заменяется автоматически)
#   ./init-letsencrypt.sh --force     # принудительный перевыпуск
#
# Состояние определяется по renewal/<domain>.conf (поле server):
#   none    -> выпуск в запрошенном режиме;
#   режим совпадает -> no-op (с --force — перевыпуск);
#   staging, запрошен боевой -> certbot delete + выпуск боевого;
#   боевой, запрошен staging -> отказ (с --force — замена на staging).
set -euo pipefail

scriptDir=$(dirname -- "$(readlink -f -- "$0")")
cd "$scriptDir"

STAGING=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --staging) STAGING=1 ;;
        --force) FORCE=1 ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
        *) echo "Неизвестный аргумент: $arg" >&2; exit 2 ;;
    esac
done

compose() { docker compose "$@"; }
# Команда в контейнере certbot (переменные PROJECT_DOMAIN/CERTBOT_EMAIL — из environment)
# (-T: без TTY — чистый stdout для подстановки $(...))
certbot_sh() { compose run --rm --no-deps -T --entrypoint sh certbot -c "$1"; }

# Резервная копия live/archive/renewal домена (восстановление при сбое выпуска)
BACKUP_DONE=0
backup_cert() {
    certbot_sh '
        b=/etc/letsencrypt/.ubc-backup
        rm -rf "$b" && mkdir -p "$b/live" "$b/archive" "$b/renewal"
        d="$PROJECT_DOMAIN"
        [ -e "/etc/letsencrypt/live/$d" ] && cp -a "/etc/letsencrypt/live/$d" "$b/live/"
        [ -e "/etc/letsencrypt/archive/$d" ] && cp -a "/etc/letsencrypt/archive/$d" "$b/archive/"
        [ -f "/etc/letsencrypt/renewal/$d.conf" ] && cp -a "/etc/letsencrypt/renewal/$d.conf" "$b/renewal/"
        true
    '
    BACKUP_DONE=1
}
restore_cert() {
    echo "### Восстановление предыдущего сертификата" >&2
    certbot_sh '
        b=/etc/letsencrypt/.ubc-backup
        d="$PROJECT_DOMAIN"
        [ -d "$b" ] || exit 0
        rm -rf "/etc/letsencrypt/live/$d" "/etc/letsencrypt/archive/$d" "/etc/letsencrypt/renewal/$d.conf"
        mkdir -p /etc/letsencrypt/live /etc/letsencrypt/archive /etc/letsencrypt/renewal
        [ -e "$b/live/$d" ] && cp -a "$b/live/$d" /etc/letsencrypt/live/
        [ -e "$b/archive/$d" ] && cp -a "$b/archive/$d" /etc/letsencrypt/archive/
        [ -f "$b/renewal/$d.conf" ] && cp -a "$b/renewal/$d.conf" /etc/letsencrypt/renewal/
        true
    '
}
drop_backup() { certbot_sh 'rm -rf /etc/letsencrypt/.ubc-backup'; }

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

# --- текущее состояние: none | staging | prod ---
# (у временного самоподписанного сертификата renewal-конфига нет)
state=$(certbot_sh '
    f="/etc/letsencrypt/renewal/$PROJECT_DOMAIN.conf"
    if [ ! -f "$f" ]; then echo none
    elif grep -q "acme-staging" "$f"; then echo staging
    else echo prod; fi
')
wanted=prod
[ "$STAGING" -eq 1 ] && wanted=staging
echo "### Сертификат: текущий — $state, запрошен — $wanted"

force_arg=""
if [ "$state" = "$wanted" ]; then
    if [ "$FORCE" -eq 0 ]; then
        echo "Сертификат ($state) уже выпущен (перевыпуск: --force). Продление — сервис certbot."
        exit 0
    fi
    force_arg="--force-renewal"
elif [ "$state" != none ]; then
    # смена CA: staging -> prod — автоматически; prod -> staging — только с --force
    if [ "$state" = prod ] && [ "$FORCE" -eq 0 ]; then
        echo "Уже выпущен боевой сертификат; замена на staging — только с --force." >&2
        exit 1
    fi
    echo "### Резервная копия и удаление сертификата $state (certbot delete)"
    backup_cert
    certbot_sh 'certbot delete --cert-name "$PROJECT_DOMAIN" --non-interactive'
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
compose exec -T nginx nginx -t

# --- 2. выпуск настоящего сертификата ---
echo "### Удаление временного сертификата (с резервной копией)"
# сохранённый ранее staging-сертификат не перезаписываем временным
[ "$BACKUP_DONE" -eq 1 ] || backup_cert
certbot_sh '
    if [ ! -f "/etc/letsencrypt/renewal/$PROJECT_DOMAIN.conf" ]; then
        rm -rf "/etc/letsencrypt/live/$PROJECT_DOMAIN" \
               "/etc/letsencrypt/archive/$PROJECT_DOMAIN"
    fi
'

echo "### Выпуск сертификата Let's Encrypt"
staging_arg=""
[ "$STAGING" -eq 1 ] && staging_arg="--staging"
if ! certbot_sh "certbot certonly --webroot -w /var/www/certbot \
    -d \"\$PROJECT_DOMAIN\" --email \"\$CERTBOT_EMAIL\" \
    --agree-tos --no-eff-email --non-interactive $staging_arg $force_arg"; then
    echo "Выпуск сертификата не удался" >&2
    restore_cert
    exit 1
fi
drop_backup

# --- 3. применение ---
echo "### Перезагрузка nginx и запуск certbot (продление)"
compose exec -T nginx nginx -s reload
compose up -d certbot

echo "Готово: https://$(certbot_sh 'printf %s "$PROJECT_DOMAIN"')"
