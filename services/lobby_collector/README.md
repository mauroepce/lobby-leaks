# Lobby Collector

Microservice para ingestar datos de la API pública de la Ley de Lobby de Chile (audiencias, viajes, donativos).

## Características

- **Autenticación**: Bearer token automático con API Key
- **Paginación automática**: Itera sobre todas las páginas disponibles
- **Ventanas temporales**: Soporta actualizaciones incrementales por rango de fechas
- **Reintentos inteligentes**: Exponential backoff para errores de red
- **Rate limiting**: Delay configurable entre requests
- **Logging estructurado**: JSON logs para observabilidad

## Instalación

```bash
cd services/lobby_collector
pip install -r requirements.txt
```

## Configuración

### Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

| Variable | Descripción | Valor por defecto | Requerido |
|----------|-------------|-------------------|-----------|
| `ENABLE_LOBBY_API` | Habilitar integración con API | `false` | No |
| `LOBBY_API_BASE_URL` | URL base de la API | `https://www.leylobby.gob.cl/api/v1` | No |
| `LOBBY_API_KEY` | API Key para autenticación | - | **Sí** (si enabled) |
| `PAGE_SIZE` | Registros por página (1-1000) | `100` | No |
| `DEFAULT_SINCE_DAYS` | Días hacia atrás por defecto | `7` | No |
| `API_TIMEOUT` | Timeout de requests (segundos) | `30.0` | No |
| `API_MAX_RETRIES` | Número de reintentos | `3` | No |
| `RATE_LIMIT_DELAY` | Delay entre requests (segundos) | `0.5` | No |
| `LOG_LEVEL` | Nivel de logging | `INFO` | No |
| `LOG_FORMAT` | Formato de logs (`json` o `text`) | `json` | No |
| `SERVICE_NAME` | Nombre del servicio | `lobby-collector` | No |

### Modo Degradado y Fallback

El servicio implementa **graceful degradation** para manejar situaciones donde la API no está disponible:

#### 🔴 Modo Deshabilitado (`ENABLE_LOBBY_API=false`)

Cuando `ENABLE_LOBBY_API=false`, el servicio:
- ✅ No realiza requests a la API
- ✅ Loggea mensaje informativo en JSON estructurado
- ✅ Termina con exit code 0 (éxito)
- ✅ No rompe cron jobs ni pipelines CI/CD

```json
{
  "timestamp": "2025-10-10T14:00:00Z",
  "service": "lobby-collector",
  "mode": "disabled",
  "message": "Lobby API integration is disabled"
}
```

**Cuándo usar**: Mientras no tengas acceso aprobado a la API oficial.

#### ⚠️ Modo Degradado (API caída/401/5xx)

Si `ENABLE_LOBBY_API=true` pero la API falla (401, 5xx, timeout), el servicio:
- ✅ No inserta datos en base de datos
- ✅ Loggea warning en JSON estructurado
- ✅ Termina con exit code 0 (no falla)
- ✅ Permite que el sistema continúe operando

```json
{
  "timestamp": "2025-10-10T14:00:00Z",
  "service": "lobby-collector",
  "status": "degraded",
  "reason": "HTTP_401",
  "status_code": 401,
  "records_processed": 0,
  "message": "API degraded, no data ingested (exiting gracefully)"
}
```

**Errores que activan degraded mode**:
- `HTTP_401` / `HTTP_403`: Autenticación rechazada
- `HTTP_500+`: Errores de servidor (después de reintentos)
- `timeout`: Timeout de red (después de reintentos)
- `network_error`: Errores de red (después de reintentos)

**Excepción**: `--test-connection` siempre se ejecuta, incluso con `ENABLE_LOBBY_API=false`

### Ejemplo `.env`

```bash
# Deshabilitar API mientras no tengas acceso
ENABLE_LOBBY_API=false

# Configurar cuando tengas acceso aprobado
# ENABLE_LOBBY_API=true
# LOBBY_API_KEY=tu_api_key_aqui

LOBBY_API_BASE_URL=https://www.leylobby.gob.cl/api/v1
PAGE_SIZE=100
DEFAULT_SINCE_DAYS=7
LOG_LEVEL=INFO

# Database connection (required for persistence)
DATABASE_URL=postgresql://postgres:password@localhost:5432/lobbyleaks
```

## Persistencia RAW (Unified Table)

El servicio ahora persiste **todos los endpoints** (audiencias, viajes, donativos) en una **tabla unificada** `LobbyEventRaw` con estrategia de upsert idempotente.

### ¿Por qué tabla unificada?

1. **Simplicidad**: Un solo esquema para todos los tipos de eventos de lobby
2. **Flexibilidad**: El campo `rawData` (JSONB) almacena el JSON completo sin pérdida de información
3. **Event Sourcing Lite**: Puedes reprocesar datos históricos cuando mejores la normalización
4. **Escalabilidad**: Agregar nuevos tipos de eventos no requiere nuevas tablas

### Esquema de la Tabla

```sql
CREATE TABLE "LobbyEventRaw" (
    id          UUID PRIMARY KEY,
    externalId  TEXT UNIQUE NOT NULL,    -- ID derivado de (kind, nombres, apellidos, fecha)
    tenantCode  TEXT NOT NULL,           -- 'CL', 'UY', etc.
    kind        TEXT NOT NULL,           -- 'audiencia' | 'viaje' | 'donativo'
    rawData     JSONB NOT NULL,          -- JSON completo del registro

    -- Campos derivados (best-effort, para queries eficientes)
    fecha       TIMESTAMPTZ,             -- Fecha principal del evento
    monto       NUMERIC,                 -- Monto (solo donativos, si aplica)
    institucion TEXT,                    -- Institución involucrada
    destino     TEXT,                    -- Destino (solo viajes)

    createdAt   TIMESTAMPTZ DEFAULT now(),
    updatedAt   TIMESTAMPTZ DEFAULT now()
);

-- Índices
CREATE UNIQUE INDEX ON "LobbyEventRaw"(externalId);
CREATE INDEX ON "LobbyEventRaw"(tenantCode);
CREATE INDEX ON "LobbyEventRaw"(kind, fecha DESC);
```

### Derivación de Campos

Los campos mínimos se derivan automáticamente del JSON con **fallbacks robustos**:

#### `externalId` (Determinista)

Como la API de Ley de Lobby no proporciona IDs únicos, generamos IDs deterministas:

```python
# Formato: kind:nombres_apellidos_fecha
# Ejemplo: "audiencia:mario_marcel_2025-01-15"
```

Si faltan campos, se usa hash SHA256 del registro completo.

#### `fecha` (Best-effort)

Mapeo por tipo de evento:

- **Audiencia**: `fecha_inicio` → `fecha` → `created_at`
- **Viaje**: `fecha_inicio` → `fecha_salida` → `fecha`
- **Donativo**: `fecha` → `fecha_donacion` → `created_at`

#### `monto` (Solo donativos)

No disponible en la API actual. Campo preparado para futuros cambios.

#### `institucion` (Best-effort)

- **Audiencia**: `sujeto_pasivo` → `institucion` → `nombre_institucion`
- **Viaje**: `institucion.nombre` → `institucion_destino`
- **Donativo**: `institucion.nombre` → `donantes[0].nombre`

#### `destino` (Solo viajes)

- **Viaje**: `destino` → `ciudad_destino` → `pais_destino`

### Upsert Idempotente

La inserción usa `INSERT ... ON CONFLICT(externalId) DO UPDATE`:

```python
await upsert_raw_event(engine, record, kind="audiencia", tenant_code="CL")
```

**Comportamiento**:
- Si `externalId` no existe → **INSERT** nuevo registro
- Si `externalId` existe → **UPDATE** `rawData` y campos derivados, actualiza `updatedAt`

Esto permite:
- Re-ingestar datos sin duplicados
- Actualizar registros si la API los modifica
- Correr el ingesta múltiples veces de forma segura

### Uso con Fixtures (Sin API)

Mientras no tengas acceso a la API (`ENABLE_LOBBY_API=false`), puedes usar fixtures locales:

```python
import json
from services.lobby_collector.ingest import ingest_audiencias

# Cargar fixture local
with open("services/lobby_collector/tests/fixtures/audiencia_sample.json") as f:
    record = json.load(f)

# Ingestar en base de datos
count = await ingest_audiencias([record], tenant_code="CL")
print(f"Procesados: {count} audiencias")
```

**Fixtures disponibles**:
- `audiencia_sample.json`: Audiencia Ministro de Hacienda
- `viaje_sample.json`: Viaje Ministra del Interior a París
- `donativo_sample.json`: Donativo a Diputado

### Funciones de Ingesta

Tres funciones para cada tipo de evento:

```python
# Ingestar audiencias
count = await ingest_audiencias(records, tenant_code="CL")

# Ingestar viajes
count = await ingest_viajes(records, tenant_code="CL")

# Ingestar donativos
count = await ingest_donativos(records, tenant_code="CL")
```

Todas implementan **graceful degradation**: si un registro falla, continúan con los siguientes.

## Staging Layer: Vista Normalizada

### `lobby_events_staging` VIEW

La vista `lobby_events_staging` proporciona una **capa de staging normalizada** sobre la tabla RAW, extrayendo campos específicos por tipo de evento y agregando metadata útil.

#### Campos Comunes

- `id`, `externalId`, `tenantCode`, `kind`: Identificadores
- `nombres`, `apellidos`, `nombresCompletos`: Persona relacionada
- `cargo`: Cargo del sujeto pasivo
- `fecha`, `year`, `month`: Campos temporales para agregaciones

#### Campos Específicos por Kind

La vista usa `CASE` statements para extraer campos según el tipo de evento:

**Audiencias**:
```sql
-- institucion: sujeto_pasivo → nombre_institucion → institucion
-- destino: NULL (solo viajes tienen destino)
-- monto: NULL (solo donativos/viajes tienen monto)
```

**Viajes**:
```sql
-- institucion: institucion.nombre → institucion_destino → organizador
-- destino: destino → CONCAT(ciudad_destino, pais_destino)
-- monto: costo_total (si está disponible)
```

**Donativos**:
```sql
-- institucion: institucion_donante → donante → institucion
-- destino: NULL
-- monto: monto (si está disponible)
```

#### Metadata

- `rawDataHash`: SHA256 del JSON completo (detección de cambios)
- `rawDataSize`: Tamaño en bytes del JSON (monitoreo)

#### Queries de Ejemplo

```sql
-- Contar eventos por año y tipo
SELECT year, kind, COUNT(*)
FROM lobby_events_staging
GROUP BY year, kind
ORDER BY year DESC, kind;

-- Buscar audiencias de una institución
SELECT nombresCompletos, fecha, cargo
FROM lobby_events_staging
WHERE kind = 'audiencia'
  AND institucion LIKE '%Hacienda%'
ORDER BY fecha DESC;

-- Viajes por destino
SELECT destino, COUNT(*) as total
FROM lobby_events_staging
WHERE kind = 'viaje' AND destino IS NOT NULL
GROUP BY destino
ORDER BY total DESC;

-- Eventos por mes (últimos 12 meses)
SELECT
  year,
  month,
  kind,
  COUNT(*) as eventos
FROM lobby_events_staging
WHERE fecha >= NOW() - INTERVAL '12 months'
GROUP BY year, month, kind
ORDER BY year DESC, month DESC;
```

#### Performance

- **Tipo**: VIEW simple (no materializada)
- **Índices**: Usa índices de la tabla `LobbyEventRaw` subyacente
- **Recomendación**: Si queries son lentas (>2s) con muchos registros (>50k), considerar materializar la vista con `REFRESH`

### Migración a MATERIALIZED VIEW (Futuro)

Si el rendimiento lo requiere:

```sql
-- Crear vista materializada
CREATE MATERIALIZED VIEW lobby_events_staging_mat AS
SELECT * FROM lobby_events_staging;

-- Crear índices
CREATE INDEX idx_staging_mat_tenant_kind ON lobby_events_staging_mat(tenantCode, kind);
CREATE INDEX idx_staging_mat_fecha ON lobby_events_staging_mat(fecha DESC);

-- Refresh manual o automático (cron)
REFRESH MATERIALIZED VIEW lobby_events_staging_mat;
```

## Uso

### CLI

```bash
# Ejecutar desde la raíz del proyecto
python -m services.lobby_collector.main [opciones]
```

### Opciones Disponibles

| Opción | Descripción | Ejemplo |
|--------|-------------|---------|
| `--since FECHA` | Fecha de inicio (YYYY-MM-DD) | `--since 2025-01-01` |
| `--until FECHA` | Fecha final (YYYY-MM-DD) | `--until 2025-01-31` |
| `--days N` | Días hacia atrás desde hoy | `--days 30` |
| `--endpoint PATH` | Endpoint de la API | `--endpoint /audiencias` |
| `--test-connection` | Probar conexión con la API | - |
| `--dry-run` | Contar registros sin procesar | - |
| `--debug` | Habilitar logging detallado | - |

### Ejemplos

#### 1. Probar conexión

```bash
python -m services.lobby_collector.main --test-connection
```

#### 2. Ingestar últimos 7 días (default)

```bash
python -m services.lobby_collector.main
```

#### 3. Ingestar últimos 30 días

```bash
python -m services.lobby_collector.main --days 30
```

#### 4. Ingestar rango de fechas específico

```bash
python -m services.lobby_collector.main \
  --since 2025-01-01 \
  --until 2025-01-31
```

#### 5. Dry-run para contar registros

```bash
python -m services.lobby_collector.main \
  --days 7 \
  --dry-run
```

#### 6. Modo debug

```bash
python -m services.lobby_collector.main \
  --days 7 \
  --debug
```

## Conceptos Clave

### Paginación Automática

El servicio maneja automáticamente la paginación de la API:

1. Comienza en `page=1`
2. Solicita `page_size` registros por página (configurable)
3. Verifica el campo `has_more` en la respuesta
4. Continúa al siguiente `page` hasta que `has_more=false`

**Memoria eficiente**: Usa `AsyncIterator` para procesar registros de uno en uno sin cargar todo en memoria.

```python
# Ejemplo de uso programático
async for record in fetch_since(datetime(2025, 1, 1)):
    # Procesa cada registro individualmente
    print(record["id"], record["sujeto_pasivo"])
```

### Ventanas Temporales (Incremental Updates)

Las ventanas temporales permiten actualizaciones incrementales:

- **`since`**: Fecha de inicio del rango (inclusive)
- **`until`**: Fecha final del rango (inclusive)

**Estrategias de ingesta**:

1. **Actualización diaria (cron)**: `--days 1` cada día
2. **Backfill semanal**: `--days 7` cada semana
3. **Rango histórico**: `--since 2024-01-01 --until 2024-12-31`

```python
# La función resolve_window() calcula las ventanas
since, until = resolve_window(days=7)
# since = hoy - 7 días
# until = hoy
```

### Reintentos y Rate Limiting

**Exponential Backoff**: Los reintentos esperan 2^n segundos:
- Intento 1: 1 segundo
- Intento 2: 2 segundos
- Intento 3: 4 segundos

**Rate Limiting**: Delay de `RATE_LIMIT_DELAY` segundos entre cada request para respetar límites de la API.

**Errores manejados**:
- `401/403`: `LobbyAPIAuthError` (error de autenticación)
- `429`: `LobbyAPIRateLimitError` (rate limit excedido)
- `5xx`: Reintentos automáticos con backoff
- Timeout/Network: Reintentos automáticos

## Testing

### Ejecutar tests

```bash
# Desde la raíz del proyecto
make lobby-collector-test

# O directamente con pytest
pytest services/lobby_collector/tests/ -v
```

### Coverage de tests

- **Paginación**: Páginas múltiples, páginas vacías, iteración completa
- **Autenticación**: Headers, errores 401/403
- **Rate limiting**: Manejo de errores 429
- **Reintentos**: Network errors, exponential backoff, agotamiento
- **Ventanas temporales**: Cálculos por días, cruces de mes/año, leap years, timezones

## Arquitectura

```
services/lobby_collector/
├── __init__.py          # Package initialization
├── settings.py          # Configuración con Pydantic
├── client.py            # HTTP client (fetch_page, auth, retries)
├── ingest.py            # Lógica de paginación y ventanas
├── main.py              # CLI entry point
├── tests/
│   ├── __init__.py
│   ├── test_pagination.py   # Tests de paginación y HTTP
│   └── test_windows.py      # Tests de ventanas temporales
├── README.md            # Esta documentación
└── requirements.txt     # Dependencias Python
```

### Separación de responsabilidades

- **`settings.py`**: Configuración centralizada (API URL, API Key, timeouts)
- **`client.py`**: Capa HTTP (autenticación, reintentos, manejo de errores)
- **`ingest.py`**: Lógica de negocio (paginación, ventanas temporales, funciones de ingesta)
- **`persistence.py`**: Persistencia RAW con upsert idempotente
- **`derivers.py`**: Extracción de campos derivados (fecha, monto, institucion, destino)
- **`main.py`**: Interfaz CLI (argparse, logging, orquestación)

## Tests

El proyecto incluye **76 tests** cubriendo todas las funcionalidades:

### Ejecutar Tests

```bash
# Todos los tests (requiere PostgreSQL)
python3 -m pytest services/lobby_collector/tests/ -v

# Solo tests de paginación (sin DB)
python3 -m pytest services/lobby_collector/tests/test_pagination.py -v

# Solo tests de persistencia RAW
python3 -m pytest services/lobby_collector/tests/test_persistence_raw.py -v

# Solo tests de staging VIEW
python3 -m pytest services/lobby_collector/tests/test_staging_view.py -v

# Solo tests de fallback/degradación
python3 -m pytest services/lobby_collector/tests/test_fallback.py -v
```

### Cobertura de Tests

| Módulo | Tests | Descripción |
|--------|-------|-------------|
| **test_pagination.py** | 18 | Paginación, autenticación, rate limiting, reintentos |
| **test_fallback.py** | 10 | Modo degradado, modo deshabilitado, graceful degradation |
| **test_windows.py** | 14 | Ventanas temporales, resolución de fechas |
| **test_persistence_raw.py** | 23 | Derivers, upsert idempotente, persistencia DB |
| **test_staging_view.py** | 20 | Vista staging, extracción por kind, metadata |
| **Total** | **76** | Cobertura completa end-to-end |

### Fixtures de Test

Los tests usan fixtures JSON realistas basados en la documentación oficial de la API:

- **`audiencia_sample.json`**: Audiencia con Ministro de Hacienda
- **`viaje_sample.json`**: Viaje internacional de Ministra del Interior
- **`donativo_sample.json`**: Donativo a Diputado con institución donante

Ubicación: `services/lobby_collector/tests/fixtures/`

## Cron & Métricas

### Ejecución Automática (GitHub Actions)

El pipeline de ingesta se ejecuta automáticamente mediante GitHub Actions:

- **Schedule**: Diario a las 7:00 AM UTC (4:00 AM Chile)
- **Workflow**: `.github/workflows/ingest-lobby.yml`
- **Trigger manual**: Disponible desde GitHub Actions UI

#### Configuración de Secrets

En GitHub Repository Settings > Secrets and variables > Actions:

| Secret | Descripción | Requerido |
|--------|-------------|-----------|
| `POSTGRES_PASSWORD` | Password de PostgreSQL | **Sí** |
| `ENABLE_LOBBY_API` | `true` para habilitar fetch | No (default: `false`) |
| `LOBBY_API_KEY` | API Key para Ley de Lobby | Solo si enabled |

| Variable | Descripción | Default |
|----------|-------------|---------|
| `LOBBY_API_BASE_URL` | URL base de la API | `https://www.leylobby.gob.cl/api/v1` |

### Ejecución Local

```bash
# Ejecutar pipeline completo (últimos 7 días)
make ingest-lobby

# Ejecutar con días personalizados
make ingest-lobby DAYS=30

# Con debug logging
ENABLE_LOBBY_API=true make ingest-lobby DAYS=7
```

### Métricas JSON

El runner genera un archivo `ingest-metrics.json` con el resultado de la ejecución:

#### Status: `ok` (Ejecución exitosa)

```json
{
  "timestamp": "2025-01-15T07:00:00Z",
  "service": "lobby-collector",
  "tenant_code": "CL",
  "days": 7,
  "status": "ok",
  "fetch": {
    "enabled": true,
    "audiencias_inserted": 150,
    "viajes_inserted": 25,
    "donativos_inserted": 10
  },
  "map": {
    "rows_processed": 185,
    "persons_created": 120,
    "persons_updated": 30,
    "orgs_created": 45,
    "orgs_updated": 10,
    "events_created": 185,
    "events_updated": 0,
    "edges_created": 185,
    "edges_updated": 0
  },
  "errors": [],
  "duration_seconds": 45.2
}
```

#### Status: `skipped` (API deshabilitada)

```json
{
  "timestamp": "2025-01-15T07:00:00Z",
  "service": "lobby-collector",
  "tenant_code": "CL",
  "days": 7,
  "status": "skipped",
  "fetch": {
    "enabled": false,
    "skipped": true,
    "audiencias_inserted": 0,
    "viajes_inserted": 0,
    "donativos_inserted": 0
  },
  "map": {
    "rows_processed": 0,
    "persons_created": 0,
    "persons_updated": 0,
    "orgs_created": 0,
    "orgs_updated": 0,
    "events_created": 0,
    "events_updated": 0,
    "edges_created": 0,
    "edges_updated": 0
  },
  "errors": [],
  "duration_seconds": 1.2
}
```

#### Status: `degraded` (Fetch falló, map ejecutado)

```json
{
  "timestamp": "2025-01-15T07:00:00Z",
  "service": "lobby-collector",
  "status": "degraded",
  "fetch": {
    "enabled": true,
    "audiencias_inserted": 0,
    "viajes_inserted": 0,
    "donativos_inserted": 0
  },
  "map": {
    "rows_processed": 50,
    "persons_created": 20,
    "events_created": 50,
    "edges_created": 50
  },
  "errors": [
    "Fetch failed: LobbyAPIAuthError: HTTP 401 Unauthorized"
  ],
  "duration_seconds": 12.5
}
```

### Safe Fallback

El pipeline **siempre termina con exit code 0** para no romper cron jobs:

- Si `ENABLE_LOBBY_API=false`: status=`skipped`, no fetch, solo map
- Si API falla (401, 5xx, timeout): status=`degraded`, map se ejecuta
- Si map falla: status=`error`, errores en array `errors`

El status real se indica en el JSON de métricas, no en el exit code.

### Monitoreo

#### GitHub Actions

1. Ver ejecuciones en **Actions** > **Scheduled Lobby Ingestion**
2. Descargar artifact `ingest-metrics-{run_id}` con métricas JSON
3. Filtrar por status en el JSON para alertas

#### Alertas (Ejemplo con jq)

```bash
# Verificar status del último run
cat ingest-metrics.json | jq -r '.status'

# Contar errores
cat ingest-metrics.json | jq '.errors | length'

# Verificar si hubo datos nuevos
cat ingest-metrics.json | jq '.map.rows_processed'
```

## Próximos Pasos

**Historias completadas**:
- ✅ **S0**: Graceful degradation y modo fallback
- ✅ **S1**: Autenticación, paginación y ventanas temporales
- ✅ **S2**: Persistencia RAW unificada con event sourcing lite
- ✅ **S3**: Staging layer normalizada con VIEW
- ✅ **S4**: Canonical graph mapping (Person, Org, Event, Edge)
- ✅ **S5**: Cron diario y métricas del pipeline

**Futuras historias**:
- **S6**: Checkpointing para resumir ingesta interrumpida
- **S7**: Métricas avanzadas (Prometheus, Grafana dashboards)
- **S8**: Validación de datos y deduplicación inteligente

## Troubleshooting

### Error: "LOBBY_API_KEY field required"

Asegúrate de configurar la variable `LOBBY_API_KEY` en tu archivo `.env`.

### Error: "Connection test failed"

1. Verifica que `LOBBY_API_BASE_URL` sea correcta
2. Confirma que tu `LOBBY_API_KEY` sea válida
3. Revisa la conectividad de red (firewall, proxy)

### Rate limit excedido (429)

Incrementa `RATE_LIMIT_DELAY` en `.env`:

```bash
RATE_LIMIT_DELAY=1.0  # 1 segundo entre requests
```

### Timeouts frecuentes

Incrementa `API_TIMEOUT` o `API_MAX_RETRIES`:

```bash
API_TIMEOUT=60.0      # 60 segundos
API_MAX_RETRIES=5     # 5 reintentos
```

## Licencia

Ver archivo `LICENSE` en la raíz del proyecto.
