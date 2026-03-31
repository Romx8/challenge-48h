#!/bin/sh
set -eu

SECRETS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../secrets" && pwd)"

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
    return
  fi
  date +%s | sha256sum | cut -d' ' -f1
}

write_if_missing() {
  target="$1"
  if [ ! -f "${SECRETS_DIR}/${target}" ]; then
    random_secret > "${SECRETS_DIR}/${target}"
    echo "Secret créé: ${SECRETS_DIR}/${target}"
  fi
}

mkdir -p "${SECRETS_DIR}"
write_if_missing "pg_super_password.txt"
write_if_missing "app_db_password.txt"
write_if_missing "repl_password.txt"
write_if_missing "grafana_admin_password.txt"

if [ ! -f "${SECRETS_DIR}/geodair_api_key.txt" ]; then
  printf '\n' > "${SECRETS_DIR}/geodair_api_key.txt"
  echo "Secret créé (vide): ${SECRETS_DIR}/geodair_api_key.txt"
fi
