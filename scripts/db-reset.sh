#!/usr/bin/env bash
set -euo pipefail
# Reaplica TODAS las migraciones (útil tras editar migration.sql con RLS)
pnpm prisma migrate reset --force --skip-seed --schema=prisma/schema.prisma
