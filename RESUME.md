# LobbyLeaks - Resumen del Proyecto

## 🎯 Visión General

**LobbyLeaks** es una plataforma de transparencia global que busca empoderar a la ciudadanía mundial exponiendo las relaciones entre lobby oficial, gasto parlamentario y financiamiento electoral. El proyecto comienza con **Chile** como primer módulo operativo, pero está diseñado con una arquitectura multi-jurisdicción escalable a cualquier país.

### Misión
Poner en un grafo abierto la relación entre lobby oficial, gasto parlamentario y financiamiento electoral antes de procesos electorales, empezando por Chile.

### Alcance
- **Módulo Chile**: Ingestión automática vía API Ley de Lobby, Transparencia Activa y Servel
- **Modo global**: Arquitectura multi-jurisdicción donde cualquier país puede añadir conectores
- **Funcionalidad "Sube tu leak"**: Permite carga manual de evidencia
- Exposición mediante API abierta, UI web y descargas CSV/JSON

## 🏗️ Arquitectura del Sistema

### Estructura General
LobbyLeaks sigue una arquitectura de **monorepo** con workspaces separados:

```
lobby-leaks/
├── apps/                    # Aplicaciones frontend/backend (vacías actualmente)
│   ├── frontend/           # Interfaz web (planificada)
│   └── backend/            # API principal (planificada)
├── services/               # Microservicios
│   ├── _template/         # Plantilla reutilizable para servicios
│   ├── mcp-hub/           # Hub MCP (Model Context Protocol)
│   └── lobby_collector/   # Colector de datos Ley de Lobby
├── clients/                # SDKs generados
│   └── ts/                # Cliente TypeScript
├── docs/                   # Documentación
├── prisma/                 # Esquemas de base de datos
└── tests/                  # Tests del proyecto
```

### Componentes Principales

#### 1. **Base de Datos (PostgreSQL + Prisma)**
- **Motor**: PostgreSQL 16 en contenedor Docker
- **ORM**: Prisma con esquema multi-tenant
- **Modelos principales**:
  - `Tenant`: Jurisdicciones (CL, UY, etc.)
  - `User`: Usuarios con roles por tenant
  - `Document`: Documentos subidos por usuarios
  - `FundingRecord`: Registros de financiamiento
  - `Leak`: Filtraciones publicadas
  - **`LobbyEventRaw`**: Tabla unificada para eventos de lobby (audiencias, viajes, donativos)
    - Almacenamiento RAW (JSONB) para event sourcing
    - Campos derivados indexados para queries eficientes
    - Upsert idempotente por `externalId`

#### 2. **Plantilla de Servicios (services/_template)**
- **Framework**: HTTPX + Pydantic + Structlog
- **Base de datos**: SQLAlchemy 2.x + psycopg3 con helpers de upsert
- **Normalización de datos**: Helpers para RUT chileno (módulo 11) y nombres
- **Características**: Cliente HTTP con retries, configuración avanzada, logging JSON
- **CLI**: Interfaz de línea de comandos con argparse
- **Testing**: 186 tests (unitarios + integración + BD + helpers) con pytest
- **Documentación completa**: [Ver README](services/_template/README.md)

#### 3. **Lobby Collector (services/lobby_collector)**
- **Framework**: HTTPX + Pydantic Settings + SQLAlchemy 2.x
- **Función**: Ingesta diaria de datos desde API Ley de Lobby de Chile con persistencia RAW
- **Características**:
  - Autenticación con Bearer Token (API Key)
  - Paginación automática con AsyncIterator
  - Ventanas temporales para actualizaciones incrementales
  - Reintentos inteligentes con exponential backoff
  - Rate limiting configurable
  - **Persistencia RAW en tabla unificada** (audiencias, viajes, donativos)
  - **Event Sourcing Lite**: JSON completo en `rawData` (JSONB)
  - **Upsert idempotente**: INSERT ON CONFLICT por `externalId`
  - **Campos derivados**: fecha, monto, institucion, destino (best-effort)
  - **IDs deterministas**: generados desde (kind, nombres, apellidos, fecha)
  - CLI con argparse (--since, --days, --test-connection, --dry-run)
- **Testing**: 56 tests (paginación + fallback + derivers + persistencia DB)
- **Documentación completa**: [Ver README](services/lobby_collector/README.md)

#### 4. **MCP Hub (services/mcp-hub)**
- **Framework**: FastAPI (Python 3.12+)
- **Protocolo**: JSON-RPC 2.0 sobre HTTP en `/rpc2`
- **Pool de conexiones**: psycopg3 con AsyncConnectionPool
- **Middleware**: Manejo de multi-tenancy via `X-Tenant-Id` header
- **Métodos stub**: `fetch_pdf`, `ocr_pdf`, `summarise_doc`, `entity_link`

#### 5. **API RESTful**
- **Especificación**: OpenAPI 3.1.0
- **Endpoints**: Actualmente solo `/rpc2` (más endpoints planificados)
- **Autenticación**: Sistema de tenants por headers

#### 6. **SDK TypeScript**
- **Generación**: OpenAPI Generator (typescript-fetch)
- **Ubicación**: `clients/ts/`
- **Regeneración**: `pnpm run gen-sdk`

## 🛠️ Stack Tecnológico

### Backend
- **Lenguaje**: Python 3.12+ (MCP Hub), Node.js 20+ (tooling)
- **Framework Web**: FastAPI
- **Base de datos**: PostgreSQL 16
- **ORM**: Prisma (schema principal) + SQLAlchemy 2.x (servicios)
- **Pool de conexiones**: psycopg3
- **Upsert operations**: INSERT ... ON CONFLICT para idempotencia
- **Contenedorización**: Docker + Docker Compose

### Frontend (Planificado)
- Interfaz web para visualización de datos
- Descargas en formato CSV/JSON
- UI de carga manual ("Sube tu leak")

### DevOps y Tooling
- **Gestión de paquetes**: pnpm (Node.js), pip (Python)
- **Linting**: ESLint
- **Testing**: Jest (Node.js), pytest (Python)
- **CI/CD**: GitHub Actions
- **Documentación API**: Redocly CLI
- **Automatización**: Make (see Makefile)

### Herramientas de Desarrollo
- **Workspaces**: pnpm workspaces
- **Monorepo**: Estructura multi-package
- **Variables de entorno**: dotenv
- **Migraciones**: Prisma Migrate

## 🔄 Flujo de Datos

### 1. Ingestión de Datos
- APIs oficiales chilenas (Ley de Lobby, Transparencia Activa, Servel)
- Conectores por jurisdicción (arquitectura extensible)
- Carga manual de documentos por usuarios

### 2. Procesamiento
- OCR de documentos PDF
- Análisis y resumen de documentos
- Linking de entidades relacionadas
- Almacenamiento con Row-Level Security (RLS)

### 3. Exposición
- API JSON-RPC para operaciones complejas
- API REST para consultas (planificada)
- Interfaz web para visualización
- Descargas directas en CSV/JSON

## 🎯 Métricas de Éxito (KPIs)

| Métrica | Meta (8 semanas) | Estado Actual |
|---------|------------------|---------------|
| Países integrados | ≥ 2 | 1 (CL) |
| Éxito de ingesta diaria | ≥ 95% | 0/0 |
| Visitantes únicos/semana | ≥ 500 | 0 |
| PRs comunidad fusionadas | ≥ 3 | 0 |
| Tiempo proceso PDF | ≤ 900s | - |
| Alertas lobby↔aporte | ≥ 20 | 0 |

## 🚀 Comandos de Desarrollo

### Setup Rápido
```bash
# Clonar y configurar
git clone https://github.com/mauroepce/lobby-leaks.git
cd lobby-leaks
cp .env.example .env

# Instalación completa
make bootstrap

# Desarrollo diario
make quick                # lint + unit + e2e
make verify              # pipeline completo
make verify-clean        # verify + limpieza
```

### Comandos Específicos
```bash
# Base de datos
make db-up               # Levantar PostgreSQL
make db-reset            # Reset + migraciones
make seed                # Cargar datos de prueba

# Tests
make test                # Tests básicos (sin DB)
make test-rls            # Tests de seguridad RLS
make test-all            # Pipeline completo (74 tests: básicos + template + RLS + e2e)

# Template
make template-test       # Tests completos del template (HTTP + DB + helpers)
make template-test-unit  # Solo unit tests (sin DB, rápido)
make template-db-test    # Solo tests de base de datos
make template-helpers-test # Solo tests de helpers (RUT + nombres)

# MCP Hub
make mcp-test-e2e        # Tests end-to-end del hub
make mcp-curl            # Verificación manual

# Lobby Collector
make lobby-collector-test # Tests del colector (23 tests)

# SDK
pnpm run gen-sdk         # Regenerar cliente TypeScript
```

## 🌍 Visión Multi-Jurisdicción

La arquitectura está diseñada para escalar globalmente:

- **Modelo Tenant**: Cada país es un tenant independiente
- **Conectores extensibles**: Nuevos países pueden agregar sus propios adaptadores
- **RLS (Row-Level Security)**: Aislamiento de datos por jurisdicción
- **API unificada**: Misma interfaz para todas las jurisdicciones

## 📋 Estado del Proyecto

**Fase actual**: MVP en desarrollo (semana 8 de 8)

### ✅ Completado
- Arquitectura base del monorepo
- Esquema de base de datos multi-tenant
- MCP Hub con stubs funcionales
- Template de servicios con conector PostgreSQL
- SQLAlchemy 2.x + upsert helpers para servicios
- Helpers de normalización (RUT chileno + nombres)
- **Lobby Collector con autenticación, paginación y ventanas temporales**
- **Lobby Collector con modo degradado y fallback (graceful degradation)**
  - Feature flag `ENABLE_LOBBY_API` para deshabilitar integración
  - Manejo de errores 401/5xx/timeout sin romper pipeline
  - Logs estructurados JSON con timestamps
  - Exit code 0 en modo degradado (no rompe cron/CI)
- **Lobby Collector con persistencia RAW unificada (E1.1-S2)**
  - Tabla `LobbyEventRaw` para audiencias, viajes y donativos
  - Event Sourcing Lite: JSON completo en `rawData` (JSONB nativo)
  - Upsert idempotente por `externalId` determinista
  - Módulo `derivers.py` para extracción de campos (fecha, monto, institucion, destino)
  - Módulo `persistence.py` con función `upsert_raw_event()`
  - Funciones de ingesta: `ingest_audiencias()`, `ingest_viajes()`, `ingest_donativos()`
  - Fixtures JSON realistas basados en API documentation
  - 56 tests (33 previos + 23 nuevos: derivers + persistencia DB)
- **Lobby Collector con staging layer normalizada (E1.1-S3)**
  - Vista SQL `lobby_events_staging` sobre LobbyEventRaw
  - Extracción de campos específicos por `kind` (CASE statements)
  - Campos temporales: `year`, `month` para agregaciones
  - Campos persona: `nombres`, `apellidos`, `nombresCompletos`, `cargo`
  - Campos por kind: `institucion`, `destino`, `monto` (según tipo de evento)
  - Metadata: `rawDataHash` (SHA256), `rawDataSize` para detección de cambios
  - VIEW simple (no materializada) para queries en tiempo real
  - 20 tests nuevos cubriendo extracción por kind y metadata
  - 76 tests totales (56 previos + 20 staging)
  - Documentación con queries de ejemplo y guía de migración a MATERIALIZED VIEW
- Pipeline CI/CD básico
- Documentación técnica completa

### 🚧 En Desarrollo
- Implementación real de métodos MCP
- **Normalización de datos chilenos (RUT, regiones)**
- Interfaz web
- Sistema de alertas

### 📋 Planificado
- Expansión a segunda jurisdicción
- OCR avanzado de documentos
- Sistema de linking de entidades
- Dashboard de métricas en tiempo real

## 📄 Licencia

MIT License - Ver [LICENSE](LICENSE) para detalles.

---

*Última actualización: 25 de septiembre de 2025*