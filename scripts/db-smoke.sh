#!/usr/bin/env bash
set -euo pipefail
# Verifica que RLS modo "deny-all" esté activo para el rol app
psql "postgresql://lobbyleaks:l0bby@127.0.0.1:5432/lobbyleaks" \
  -v ON_ERROR_STOP=on \
  -c 'SET ROLE lobbyleaks;' \
  -c 'SELECT count(*) FROM "User";' \
  -c 'SELECT count(*) FROM "Document";' \
  -c 'SELECT count(*) FROM "FundingRecord";' \
  -c 'SELECT count(*) FROM "Tenant";' \
echo "Smoke-test RLS ejecutado (debería devolver 0 filas con datos vacíos)."
