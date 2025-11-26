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
- **`ingest.py`**: Lógica de negocio (paginación, ventanas temporales)
- **`main.py`**: Interfaz CLI (argparse, logging, orquestación)

## Pipeline RAW → STAGING → CANONICAL

El servicio implementa un pipeline de tres capas para transformar datos desde el formato raw de la API hasta un grafo de conocimiento normalizado.

### Arquitectura del Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   API Raw   │ --> │   STAGING    │ --> │   CANONICAL     │
│   (JSONB)   │     │    (VIEW)    │     │    (GRAPH)      │
└─────────────┘     └──────────────┘     └─────────────────┘
      │                    │                      │
      ▼                    ▼                      ▼
LobbyEventRaw     lobby_events_staging    Person, Org,
  (tabla)            (SQL VIEW)           Event, Edge
```

### Capa 1: RAW (Event Sourcing)

**Tabla**: `LobbyEventRaw`

Almacena el JSON completo de la API sin transformaciones:

```sql
-- Ejemplo de registro raw
{
  "id": "uuid-123",
  "externalId": "audiencia:mario_marcel_2025-01-15",
  "kind": "audiencia",
  "rawData": {
    "nombres": "Mario",
    "apellidos": "Marcel",
    "cargo": "Ministro de Hacienda",
    "sujeto_pasivo": "Ministerio de Hacienda",
    "fecha_inicio": "2025-01-15T10:00:00Z"
  }
}
```

**Ventajas**:
- ✅ Event sourcing: Reprocesar datos sin llamadas a la API
- ✅ Flexibilidad: Sin pérdida de información original
- ✅ Auditoría: Trazabilidad completa de cambios

### Capa 2: STAGING (Normalización)

**VIEW**: `lobby_events_staging`

Vista SQL que extrae y normaliza campos del JSONB:

```sql
SELECT
  id,
  "externalId",
  kind,
  -- Campos normalizados
  ("rawData"::jsonb)->>'nombres' as nombres,
  ("rawData"::jsonb)->>'apellidos' as apellidos,
  CONCAT_WS(' ', ("rawData"::jsonb)->>'nombres', ("rawData"::jsonb)->>'apellidos') as "nombresCompletos",

  -- Campos específicos por kind (CASE statements)
  CASE
    WHEN kind = 'audiencia' THEN ("rawData"::jsonb)->>'sujeto_pasivo'
    WHEN kind = 'viaje' THEN ("rawData"::jsonb)->'institucion'->>'nombre'
    WHEN kind = 'donativo' THEN ("rawData"::jsonb)->>'institucion_donante'
  END as institucion,

  -- Metadata
  ENCODE(SHA256(("rawData"::jsonb)::text::bytea), 'hex') as "rawDataHash",
  LENGTH(("rawData"::jsonb)::text) as "rawDataSize"
FROM "LobbyEventRaw";
```

**Ventajas**:
- ✅ Queries eficientes sin parsing manual de JSONB
- ✅ Campos derivados calculados una sola vez
- ✅ Vista materializable para mejor performance

**Helpers de normalización**:
```python
from services.lobby_collector.staging import (
    normalize_person_name,  # "Juan Pérez" -> "juan perez"
    normalize_rut,          # "12.345.678-5" -> "123456785"
    validate_rut,           # Validación módulo 11
)
```

### Capa 3: CANONICAL (Knowledge Graph)

**Tablas**: `Person`, `Organisation`, `Event`, `Edge`

Grafo de conocimiento normalizado para análisis de relaciones:

```
┌──────────┐                  ┌──────────────┐
│  Person  │                  │ Organisation │
├──────────┤                  ├──────────────┤
│ rut      │                  │ rut          │
│ nombres  │                  │ name         │
│ apellidos│                  │ tipo         │
└────┬─────┘                  └──────┬───────┘
     │                               │
     │      ┌───────┐                │
     └─────>│ Edge  │<───────────────┘
            ├───────┤
            │ label │ (MEETS, TRAVELS_TO, CONTRIBUTES)
            │ event │
            └───┬───┘
                │
           ┌────▼────┐
           │  Event  │
           ├─────────┤
           │ kind    │
           │ fecha   │
           └─────────┘
```

**Reglas de Edges por tipo**:

1. **Audiencia**: `Person MEETS Organisation`
   ```
   [Mario Marcel] --MEETS--> [Ministerio de Hacienda]
   ```

2. **Viaje**: `Person TRAVELS_TO Organisation`
   ```
   [Gloria Hutt] --TRAVELS_TO--> [ONU]
   ```

3. **Donativo**: `Organisation CONTRIBUTES Person`
   ```
   [Empresa S.A.] --CONTRIBUTES--> [Juan Pérez]
   ```

**Deduplicación por claves naturales**:
- **Person**: `(tenantCode, rut)` o `(tenantCode, normalizedName)`
- **Organisation**: `(tenantCode, rut)` o `(tenantCode, normalizedName)`
- **Event**: `(tenantCode, externalId, kind)`
- **Edge**: `(eventId, fromPersonId, fromOrgId, toPersonId, toOrgId, label)`

### Ejecutar el Pipeline Completo

```python
from services.lobby_collector.ingest import map_staging_to_canonical

# Mapear staging a canonical (idempotente)
stats = map_staging_to_canonical(
    kind="audiencia",  # Filtrar por tipo (opcional)
    limit=1000,        # Limitar registros (opcional)
)

print(f"Procesados: {stats['rows_processed']}")
print(f"Personas creadas: {stats['persons_created']}")
print(f"Organizaciones creadas: {stats['orgs_created']}")
print(f"Relaciones creadas: {stats['edges_created']}")
```

**Idempotencia garantizada**: Ejecutar múltiples veces no crea duplicados.

### Queries de Ejemplo

#### 1. Buscar audiencias de un Ministro

```sql
SELECT
  e.fecha,
  o.name as institucion,
  edge.metadata->>'cargo' as cargo
FROM "Edge" edge
JOIN "Person" p ON edge."fromPersonId" = p.id
JOIN "Organisation" o ON edge."toOrgId" = o.id
JOIN "Event" e ON edge."eventId" = e.id
WHERE p."normalizedName" = 'mario marcel'
  AND edge.label = 'MEETS'
ORDER BY e.fecha DESC;
```

#### 2. Encontrar relaciones entre personas

```sql
-- Personas que se reunieron con la misma organización
SELECT
  p1."nombresCompletos" as persona1,
  p2."nombresCompletos" as persona2,
  o.name as organizacion_comun
FROM "Edge" e1
JOIN "Edge" e2 ON e1."toOrgId" = e2."toOrgId" AND e1.id != e2.id
JOIN "Person" p1 ON e1."fromPersonId" = p1.id
JOIN "Person" p2 ON e2."fromPersonId" = p2.id
JOIN "Organisation" o ON e1."toOrgId" = o.id
WHERE e1.label = 'MEETS' AND e2.label = 'MEETS';
```

#### 3. Top organizaciones por número de audiencias

```sql
SELECT
  o.name,
  o.tipo,
  COUNT(*) as total_audiencias
FROM "Edge" edge
JOIN "Organisation" o ON edge."toOrgId" = o.id
JOIN "Event" e ON edge."eventId" = e.id
WHERE edge.label = 'MEETS'
  AND e.kind = 'audiencia'
GROUP BY o.id, o.name, o.tipo
ORDER BY total_audiencias DESC
LIMIT 10;
```

### Testing del Pipeline

```bash
# Tests unitarios (61 tests)
pytest services/lobby_collector/tests/test_staging.py -v          # 32 tests
pytest services/lobby_collector/tests/test_canonical_mapper.py -v  # 18 tests
pytest services/lobby_collector/tests/test_canonical_persistence.py -v  # 11 tests
```

## Próximos Pasos

**Completado (E1.1)**:
- ✅ **S1**: Autenticación y paginación
- ✅ **S2**: Persistencia RAW (tabla unificada)
- ✅ **S3**: Staging layer (VIEW normalizada)
- ✅ **S4**: Canonical graph (grafo de conocimiento)

**Futuras mejoras**:
- **S5**: Métricas y observabilidad (Prometheus, Grafana)
- **S6**: API GraphQL para queries del grafo
- **S7**: Detección de conflictos de interés
- **S8**: Visualización de redes de influencia

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
