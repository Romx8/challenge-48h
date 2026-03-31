#!/bin/sh
set -eu

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
PRIMARY_HOST="${PRIMARY_HOST:-postgres-primary}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"

if [ ! -s "${PGDATA}/PG_VERSION" ]; then
  rm -rf "${PGDATA:?}"/*

  REPL_PASSWORD="$(cat "${REPL_PASSWORD_FILE}")"
  export PGPASSWORD="${REPL_PASSWORD}"

  until pg_basebackup \
    -h "${PRIMARY_HOST}" \
    -p "${PRIMARY_PORT}" \
    -U "${REPL_USER}" \
    -D "${PGDATA}" \
    -R \
    -X stream \
    -c fast; do
    echo "Replica en attente de la primaire..."
    sleep 2
  done

  unset PGPASSWORD
fi

exec docker-entrypoint.sh postgres -c hot_standby=on
