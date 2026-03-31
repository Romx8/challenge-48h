#!/bin/bash
set -euo pipefail

APP_DB_PASSWORD="$(cat "${APP_DB_PASSWORD_FILE}")"
REPL_PASSWORD="$(cat "${REPL_PASSWORD_FILE}")"

psql -v ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER}" \
  --dbname postgres \
  --set app_db_name="${APP_DB_NAME}" \
  --set app_db_user="${APP_DB_USER}" \
  --set app_db_password="${APP_DB_PASSWORD}" \
  --set repl_user="${REPL_USER}" \
  --set repl_password="${REPL_PASSWORD}" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN', :'app_db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_db_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'app_db_user', :'app_db_password')
\gexec

SELECT format('CREATE ROLE %I REPLICATION LOGIN', :'repl_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'repl_user')
\gexec

SELECT format('ALTER ROLE %I WITH REPLICATION LOGIN PASSWORD %L', :'repl_user', :'repl_password')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'app_db_name', :'app_db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'app_db_name')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'app_db_name', :'app_db_user')
\gexec
EOSQL

cat <<EOF_HBA >> "${PGDATA}/pg_hba.conf"
host replication ${REPL_USER} all scram-sha-256
hostssl replication ${REPL_USER} all scram-sha-256
host all ${APP_DB_USER} all scram-sha-256
hostssl all ${APP_DB_USER} all scram-sha-256
EOF_HBA

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname postgres -c "SELECT pg_reload_conf();"
