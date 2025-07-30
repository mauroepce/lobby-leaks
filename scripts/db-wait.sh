#!/usr/bin/env bash
set -euo pipefail
# Espera hasta que Postgres acepte conexiones (host expuesto a 5432)
until pg_isready -h 127.0.0.1 -p 5432 -d lobbyleaks -U lobbyleaks >/dev/null 2>&1; do
  echo "Esperando a Postgres…"
  sleep 1
done
echo "Postgres listo."
