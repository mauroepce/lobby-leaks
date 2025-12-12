# InfoLobby Sync Service

Fetches lobby data from InfoLobby SPARQL endpoint (datos.infolobby.cl).

## Data Sources

| Campo | Valor |
|-------|-------|
| **Nombre** | InfoLobby SPARQL |
| **Tipo** | Oficial (Consejo para la Transparencia) |
| **País** | Chile |
| **Endpoint** | `http://datos.infolobby.cl/sparql` |
| **Formato** | SPARQL/RDF (JSON results) |
| **Epic** | E1.2 |

### Available Data Types

| Type | RDF Class | Description |
|------|-----------|-------------|
| Audiencias | `cplt:RegistroAudiencia` | Meeting records |
| Viajes | `cplt:Viaje` | Travel records |
| Donativos | `cplt:Donativo` | Gift/donation records |

## Setup

```bash
cd services/info_lobby_sync
pip install -r requirements.txt
```

## Configuration

Environment variables (or `.env` file):

```bash
INFOLOBBY_SPARQL_ENDPOINT=http://datos.infolobby.cl/sparql
INFOLOBBY_DEFAULT_GRAPH=http://datos.infolobby.cl/infolobby
SPARQL_BATCH_SIZE=1000
HTTP_TIMEOUT=30.0
HTTP_MAX_RETRIES=3
ENABLE_INFOLOBBY_SYNC=true
```

## Usage

### Fetching Data

```python
from info_lobby_sync.fetcher import SPARQLClient, fetch_all

# Fetch all audiencias
with SPARQLClient() as client:
    for audiencia in fetch_all("audiencias", batch_size=1000):
        print(audiencia["codigoURI"])

# Fetch specific type with limit
from info_lobby_sync.fetcher import fetch_viajes
records = fetch_viajes(limit=100, offset=0)
```

### Parsing Results

```python
from info_lobby_sync.parser import parse_audiencia

# Parse single record
parsed = parse_audiencia(raw_record)
print(parsed.codigo_uri)
print(parsed.pasivo.nombre)  # Parsed official name
print(parsed.activos)        # List of lobbyist names
print(parsed.checksum)       # SHA256 for change detection
```

## Testing

```bash
pytest services/info_lobby_sync/tests/ -v
```

## WAF Notes

The endpoint is behind a Fortinet WAF that requires:
- `Referer: http://datos.infolobby.cl/sparql` header
- Standard browser-like User-Agent

The fetcher handles this automatically.

## Schema Documentation

See [docs/infolobby/sparql-schema.md](../../docs/infolobby/sparql-schema.md) for complete field documentation.
