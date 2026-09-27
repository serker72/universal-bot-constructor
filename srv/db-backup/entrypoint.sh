#!/bin/sh
# Ежедневный дамп PostgreSQL + ротация по числу копий (сервис db-backup).
# Дампы — custom-формат pg_dump (-Fc: сжатие, выборочное восстановление
# через pg_restore) в $BACKUP_DIR (хостовый POSTGRES_BACKUPS_DIR).
# Время дампа POSTGRES_BACKUP_AT — ЧЧ:ММ в UTC (часовой пояс контейнера).
# Имена файлов: <db>_ГГГГ-ММ-ДД_ЧЧММ.dump (сортировка = хронология).
set -eu

: "${PGDATABASES:?PGDATABASES is required}"
: "${POSTGRES_BACKUP_AT:?POSTGRES_BACKUP_AT is required}"
: "${POSTGRES_BACKUP_KEEP:?POSTGRES_BACKUP_KEEP is required}"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/postgresql/backups}"
PGHOST="${PGHOST:-postgres}"

log() { echo "[db-backup] $(date -u '+%Y-%m-%d %H:%M:%S') $*"; }

run_backups() {
    ts="$(date -u +%Y-%m-%d_%H%M)"
    for db in $PGDATABASES; do
        out="$BACKUP_DIR/${db}_${ts}.dump"
        if pg_dump -Fc -f "$out" "$db"; then
            log "dump ok: $(basename "$out") ($(du -h "$out" | cut -f1))"
        else
            log "dump FAILED: $db"
            rm -f "$out"
            continue
        fi
        # ротация: оставить последние $POSTGRES_BACKUP_KEEP дампов этой БД
        ls -1t "$BACKUP_DIR"/"${db}"_*.dump 2>/dev/null | \
            tail -n +"$((POSTGRES_BACKUP_KEEP + 1))" | \
            xargs -r rm -f --
    done
}

# HH:MM -> минуты. Ведущие нули снимаются sed-ом: dash/busybox ash
# трактуют "09" как осьмеричную ошибку (10#NN при этом не поддерживается).
to_minutes() {
    h=$(echo "$1" | cut -d: -f1 | sed 's/^0*\([0-9]\)/\1/')
    m=$(echo "$1" | cut -d: -f2 | sed 's/^0*\([0-9]\)/\1/')
    echo $((h * 60 + m))
}

# Секунды до ближайшего наступления POSTGRES_BACKUP_AT (UTC).
# Busybox date не умеет date -d "today HH:MM" — арифметика по минутам дня.
seconds_until() {
    tgt=$(to_minutes "$POSTGRES_BACKUP_AT")
    cur=$(to_minutes "$(date -u +%H:%M)")
    diff=$(( (tgt - cur + 1440) % 1440 ))
    if [ "$diff" -eq 0 ]; then
        echo 0   # находимся в целевой минуте — дамп сразу
    else
        echo $((diff * 60))
    fi
}

log "start: db=[$PGDATABASES] daily_at=$POSTGRES_BACKUP_AT (UTC) keep=$POSTGRES_BACKUP_KEEP dir=$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
while true; do
    sleep "$(seconds_until)"
    run_backups
    # пауза за пределы текущей минуты — защита от повторного дампа в ней же
    sleep 60
done