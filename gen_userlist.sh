#!/bin/bash
# Генерация userlist.txt для pgbouncer (auth_type=scram-sha-256):
# pgbouncer требует plaintext-пароли (или SCRAM-верификаторы) в userlist.
# Файл не хранится в git (.gitignore), создаётся с правами 600.
set -euo pipefail
umask 077

scriptDir="$(dirname -- "$(readlink -f -- "$0")")"
envFile="${scriptDir}/.env"

# Значение переменной из .env: точное совпадение имени, комментарии
# игнорируются, обрамляющие кавычки снимаются, пробелы внутри сохраняются
env_value() {
    local name="$1" line value
    line="$(grep -E "^[[:space:]]*${name}=" "$envFile" | tail -n 1 || true)"
    if [ -z "$line" ]; then
        echo "gen_userlist.sh: переменная ${name} не найдена в ${envFile}" >&2
        exit 1
    fi
    value="${line#*=}"
    value="${value%$'\r'}"
    if [[ "$value" =~ ^\"(.*)\"$ ]] || [[ "$value" =~ ^\'(.*)\'$ ]]; then
        value="${BASH_REMATCH[1]}"
    fi
    printf '%s' "$value"
}

POSTGRES_USER="$(env_value POSTGRES_USER)"
POSTGRES_PASSWORD="$(env_value POSTGRES_PASSWORD)"
POSTGRES_TEST_USER="$(env_value POSTGRES_TEST_USER)"
POSTGRES_TEST_PASSWORD="$(env_value POSTGRES_TEST_PASSWORD)"

target="${scriptDir}/srv/pgbouncer/userlist.txt"
# pgbouncer в контейнере (edoburu/pgbouncer) работает от uid/gid 70
PGBOUNCER_GID=70

# Старый файл может принадлежать другому пользователю (например, 70) —
# удаляем и создаём заново (нужны права на запись в каталог)
rm -f "$target"
# Заполняем файл userlist.txt
cat > "$target" << EOF
"postgres" "${POSTGRES_PASSWORD}"
"${POSTGRES_USER}" "${POSTGRES_PASSWORD}"
"${POSTGRES_TEST_USER}" "${POSTGRES_TEST_PASSWORD}"
EOF
# Владелец — текущий пользователь (чтение/правка на хосте), группа — gid 70
# (чтение pgbouncer), права 640: остальным пользователям хоста файл недоступен.
chmod 640 "$target"
if chgrp "$PGBOUNCER_GID" "$target" 2>/dev/null; then
    :
elif command -v docker >/dev/null 2>&1; then
    # без sudo: chgrp в одноразовом контейнере (root внутри контейнера)
    docker run --rm -v "$(dirname -- "$target"):/p" alpine:3 \
        chgrp "$PGBOUNCER_GID" "/p/$(basename -- "$target")"
else
    echo "gen_userlist.sh: выполните: sudo chgrp ${PGBOUNCER_GID} ${target}" >&2
    echo "  (иначе pgbouncer не прочитает файл с правами 640)" >&2
    exit 1
fi
