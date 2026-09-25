#!/bin/bash
###############################################################################
# PostgreSQL Docker multiple databases creation script:
#  postgres:
#    image: postgres:15
#    environment:
#      POSTGRES_MULTIPLE_DATABASES: db1::u1::p1|db2::u2::p2|db3::u3::p3
#      POSTGRES_PASSWORD: postgres
#    ports:
#      - "5432:5432"
#    volumes:
#      - ./create-multiple-postgresql-databases.sh:/docker-entrypoint-initdb.d/create-multiple-postgresql-databases.sh
#
# Пользователи приложения создаются БЕЗ SUPERUSER (владелец своей БД):
# утечка пароля / SQL-инъекция не дают COPY ... PROGRAM и доступа к чужим БД.
# Имена и пароль экранируются psql (:"var" — идентификатор, %L — литерал).
#
# Скрипт идемпотентен: для уже существующего кластера (init-скрипты больше
# не выполняются) его можно запустить повторно — роли будут понижены
# до NOSUPERUSER, недостающие БД созданы:
#   docker exec ubc-postgres bash /docker-entrypoint-initdb.d/create-multiple-postgresql-databases.sh
###############################################################################
set -e
set -u

function create_user_and_database() {
	local spec="$1"
	local database="${spec%%::*}"
	local rest="${spec#*::}"
	local owner="${rest%%::*}"
	local pass="${rest#*::}"
	echo "  Creating user '$owner' and database '$database'"
	# пароль передаётся через окружение (\getenv), а не argv psql
	UBC_DB_PASS="$pass" psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" \
		-v database="$database" -v owner="$owner" <<-'EOSQL'
		\getenv pass UBC_DB_PASS
		SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'owner', :'pass')
		WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner') \gexec
		SELECT format(
		    'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
		    :'owner', :'pass'
		) \gexec
		SELECT format('CREATE DATABASE %I OWNER %I', :'database', :'owner')
		WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database') \gexec
		ALTER DATABASE :"database" OWNER TO :"owner";
		GRANT ALL ON DATABASE :"database" TO :"owner";
		\connect :"database"
		GRANT ALL ON SCHEMA public TO :"owner";
	EOSQL
}

if [ -n "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
	echo "Multiple database creation requested"
	IFS='|' read -r -a specs <<< "$POSTGRES_MULTIPLE_DATABASES"
	for db in "${specs[@]}"; do
		create_user_and_database "$db"
	done
	echo "Multiple databases created"
fi
