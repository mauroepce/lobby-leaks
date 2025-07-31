# LobbyLeaks
[![CI](https://github.com/mauroepce/lobby-leaks/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mauroepce/lobby-leaks/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OpenAPI](https://img.shields.io/badge/openapi-validated-brightgreen?logo=openapi)](docs/openapi.yaml)

> Transparencia global del lobby — primer módulo operativo: **Chile** 🇨🇱  

## ¿Qué es LobbyLeaks?

Conoce la misión, el alcance global y las métricas en nuestro  
[Project Charter](docs/charter.md).

## What is LobbyLeaks?

Read the project’s purpose, global scope, and KPIs in the  
[Project Charter](docs/charter.md).

## Security & Conduct
- Issues or violations? email **[maintainer@lobbyleaks.com](mailto:maintainer@lobbyleaks.com)**
- Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

## Quick start (≤ 5 min)

```bash
```bash
git clone https://github.com/mauroepce/lobby-leaks.git
cd lobby-leaks

# 0) optional but recommended: create & activate Python venv
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 1) copy env template and adjust if needed
cp .env.example .env         # default uses Postgres on localhost:5432

# 2) install ALL dependencies (Node + Python)
make install

# 3) bootstrap database (Docker) and apply schema
make db-reset

# 4) run test suites
make test                    # Jest + Pytest (excludes RLS)
RUN_RLS=1 make test-rls      # Row-Level-Security regression tests

# 5) lint code
make lint
```
> Tip: Postgres is started via Docker(`make db-up`).   
> The health-check relies on `pg_isready`, following the official recommendation for Dockerised Postgres containers.

## SDK TypeScript

```bash
pnpm run gen-sdk   # Regenera clients/ts/ desde docs/openapi.yaml
```
> *El cliente se genera con OpenAPI Generator* (`typescript-fetch`) y se guarda en
`clients/ts/`.   
> *No edites archivos generados a mano;* en su lugar actualiza
`docs/openapi.yaml` y vuelve a ejecutar el comando.

<details>
<summary>Available Make targets</summary>

| Target | Purpose |
|--------|---------|
| `make install` | Install Node (pnpm) + Python deps |
| `make db-up` / `make db-wait` | Spin up Postgres container & wait for `pg_isready` |
| `make db-reset` | Reapply all Prisma migrations |
| `make test` | Jest + Pytest (marker **not rls**) |
| `make test-rls` | RLS smoke tests (`RUN_RLS=1`) |
| `make lint` | ESLint |
| `make gen-sdk` | Regenerate TypeScript client |

</details>

> **`RUN_RLS` flag** – The RLS suite touches Postgres roles and adds ~10 s, so it’s opt-in to keep day-to-day `make test` snappy.

---

### Requirements
* **Node** ≥ 20.x  
* **Python** ≥ 3.12  
* **Docker** (for local Postgres 16)

---

### Contributing
Please read our [**CONTRIBUTING guide**](CONTRIBUTING.md) before opening an issue or PR.

