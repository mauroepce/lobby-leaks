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
- **`ingest.py`**: Lógica de negocio (paginación, ventanas temporales)
- **`main.py`**: Interfaz CLI (argparse, logging, orquestación)

## Próximos Pasos

Esta historia (feat/e1.1-s1-lobby-auth-pagination) implementa la base de ingesta.

**Futuras historias**:
- **s2**: Guardar datos en PostgreSQL (prisma)
- **s3**: Normalización de datos chilenos (RUT, regiones, etc.)
- **s4**: Checkpointing para resumir ingesta interrumpida
- **s5**: Métricas y observabilidad (Prometheus, Grafana)
- **s6**: Validación de datos y manejo de duplicados

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
