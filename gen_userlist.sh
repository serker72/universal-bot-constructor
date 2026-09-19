#!/bin/bash
# Генерация userlist.txt для pgbouncer (auth_type=scram-sha-256):
# pgbouncer требует plaintext-пароли (или SCRAM-верификаторы) в userlist.
# Файл не хранится в git (.gitignore).
scriptDir=`dirname -- "$( readlink -f -- "$0"; )"`
export $(grep -e 'POSTGRES_USER' -e 'POSTGRES_PASSWORD' -e 'POSTGRES_TEST_USER' -e 'POSTGRES_TEST_PASSWORD' $scriptDir/.env | xargs)
# Заполняем файл userlist.txt
cat > $scriptDir/srv/pgbouncer/userlist.txt << EOF
"postgres" "${POSTGRES_PASSWORD}"
"${POSTGRES_USER}" "${POSTGRES_PASSWORD}"
"${POSTGRES_TEST_USER}" "${POSTGRES_TEST_PASSWORD}"
EOF