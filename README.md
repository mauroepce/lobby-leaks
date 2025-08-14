# LobbyLeaks

[![CI](https://github.com/mauroepce/lobby-leaks/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mauroepce/lobby-leaks/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OpenAPI](https://img.shields.io/badge/openapi-validated-brightgreen?logo=openapi)](docs/openapi.yaml)

> Transparencia global del lobby — primer módulo operativo: **Chile** 🇨🇱

## ¿Qué es LobbyLeaks?

Conoce misión, alcance y métricas en el [Project Charter](docs/charter.md).

## What is LobbyLeaks?

Read purpose, scope and KPIs in the [Project Charter](docs/charter.md).

## Security & Conduct

- Issues or violations? **[maintainer@lobbyleaks.com](mailto:maintainer@lobbyleaks.com)**
- Please read our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Quick start (≤ 5 min)

```bash
git clone https://github.com/mauroepce/lobby-leaks.git
cd lobby-leaks

# (opcional) entorno Python
python -m venv .venv && source .venv/bin/activate   # Win: .venv\Scripts\activate

# env base
cp .env.example .env

# instala deps del repo + hub MCP
make bootstrap

# ruta rápida diaria: lint + unit + e2e del hub (Docker)
make quick
```

Pipeline completo (incluye RLS):

```bash
make verify         # instala, sube DB, lint, unit, RLS, e2e MCP
make verify-clean   # igual que verify y luego baja contenedores/volúmenes
```

Requisitos: Node 20+, Python 3.12+, Docker (Postgres 16 en contenedor).

## SDK TypeScript

```bash
pnpm run gen-sdk   # Regenera clients/ts/ desde docs/openapi.yaml
```

El cliente se genera con OpenAPI Generator (typescript-fetch) en `clients/ts/`.

No edites archivos generados; modifica `docs/openapi.yaml` y vuelve a generar.

## Make targets

### Atajos "todo en uno"

- `make bootstrap` — instala deps del repo + MCP hub
- `make quick` — lint + unit + e2e del hub
- `make verify` — flujo completo (DB, lint, unit, RLS, e2e)
- `make verify-clean` — igual que verify y luego limpia todo

### Base

- `make install` — deps Node/Python del repo
- `make lint` — ESLint
- `make test` — Jest + Pytest (excluye RLS)
- `RUN_RLS=1 make test-rls` — smoke de Row-Level-Security (requiere DB)

### DB / MCP (Docker)

- `make db-up` / `make db-reset` — subir DB / resetear + migrar
- `make mcp-test-e2e` — build imagen → subir DB → arrancar hub → esperar /rpc2 → tests del hub → apagar hub
- `make mcp-curl` — comprobación manual:
  - sin header → 400
  - con X-Tenant-Id: CL → 501
- `make mcp-down` — bajar todo (incluye volúmenes)

Los comandos e2e crean la red `*_default` de compose, levantan Postgres y pasan `DATABASE_URL` al contenedor del hub.

---

### Contributing
Please read our [**CONTRIBUTING guide**](CONTRIBUTING.md) before opening an issue or PR.

