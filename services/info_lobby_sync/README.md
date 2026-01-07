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
| **Epic** | E1.2, E1.3 |

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
DATABASE_URL=postgresql://user:pass@localhost:5432/lobbyleaks
```

## Pipeline

```
SPARQL Endpoint → fetcher.py → parser.py → events.py → participation.py → merge.py → persistence.py → report.py
     │                │            │            │              │              │            │             │
     └── Raw JSON     └── Typed    └── Typed    └── Graph      └── Dedup      └── UPSERT   └── JSON
                          records      events       edges          + match        to DB        metrics
```

## Usage

### Full Sync Example

```python
from services.info_lobby_sync.fetcher import SPARQLClient, fetch_audiencias
from services.info_lobby_sync.parser import parse_all_audiencias
from services.info_lobby_sync.merge import merge_records_in_memory
from services.info_lobby_sync.persistence import persist_merge_result
from services.info_lobby_sync.report import create_report, save_report, FetchMetrics
from services._template.db.connector import get_engine
from datetime import datetime

# 1. Fetch
with SPARQLClient() as client:
    raw_records = fetch_audiencias(client, limit=100)

# 2. Parse
parsed = parse_all_audiencias(raw_records)
parsed_dicts = [vars(p) for p in parsed]  # Convert to dicts

# 3. Merge (dedup + match existing)
engine = get_engine("postgresql://...")
merge_result = merge_records(parsed_dicts, engine, tenant_code="CL")

# 4. Persist
persistence_result = persist_merge_result(engine, merge_result)

# 5. Report
report = create_report(
    tenant_code="CL",
    fetch_metrics=FetchMetrics(
        audiencias_fetched=len(raw_records),
        total_fetched=len(raw_records),
    ),
    merge_result=merge_result,
    persistence_result=persistence_result,
)
filepath = save_report(report)
print(f"Report saved: {filepath}")
```

### Fetching Data

```python
from services.info_lobby_sync.fetcher import SPARQLClient, fetch_all

# Fetch all audiencias with pagination
with SPARQLClient() as client:
    for audiencia in fetch_all("audiencias", batch_size=1000):
        print(audiencia["codigoURI"])

# Fetch specific type with limit
from services.info_lobby_sync.fetcher import fetch_viajes
records = fetch_viajes(limit=100, offset=0)
```

### Parsing Results

```python
from services.info_lobby_sync.parser import parse_audiencia

parsed = parse_audiencia(raw_record)
print(parsed.codigo_uri)
print(parsed.pasivo.nombre)  # Parsed official name
print(parsed.activos)        # List of lobbyist names
print(parsed.checksum)       # SHA256 for change detection
```

### Extracting Events (E1.3-S1)

```python
from services.info_lobby_sync.parser import parse_all_audiencias
from services.info_lobby_sync.events import extract_events

# Parse raw records
parsed_audiencias = parse_all_audiencias(raw_records)

# Extract typed events with normalized entity references
events = extract_events(audiencias=parsed_audiencias)

for event in events:
    print(f"{event.event_type}: {event.external_id}")
    print(f"  Pasivo: {event.pasivo_ref}")
    print(f"  Activos: {event.activos_refs}")
```

### Extracting Participations (E1.3-S2)

```python
from services.info_lobby_sync.events import extract_events
from services.info_lobby_sync.participation import (
    extract_participations,
    load_persons_dict,
    load_organisations_dict,
)

# 1. Extract events from parsed records
events = extract_events(audiencias=parsed_audiencias, viajes=parsed_viajes)

# 2. Load canonical entities from DB
engine = get_engine("postgresql://...")
persons = load_persons_dict(engine, tenant_code="CL")
orgs = load_organisations_dict(engine, tenant_code="CL")

# 3. Extract participation edges (exact name matching)
result = extract_participations(events, persons, orgs)

print(f"Created {result.total_edges} edges")
print(f"Skipped {result.total_skipped} unmatched refs")
print(f"Edges by role: {result.edges_by_role}")
```

Participation roles:
- `PASIVO`: Public official in meeting/receiving gift
- `ACTIVO`: Lobbyist in meeting
- `REPRESENTADO`: Organisation represented in meeting
- `FINANCIADOR`: Organisation funding travel
- `DONANTE`: Organisation giving donation

### Merging Entities

```python
from services.info_lobby_sync.merge import merge_records_in_memory

# In-memory merge (for testing)
result = merge_records_in_memory(parsed_dicts)
print(f"Persons: {len(result.persons)}")
print(f"Orgs: {len(result.organisations)}")
print(f"Duplicates found: {result.duplicates_found}")

# With DB lookup
from services.info_lobby_sync.merge import merge_records
result = merge_records(parsed_dicts, engine, tenant_code="CL")
```

### Reports

Reports are saved to `data/info_lobby/reports/` with timestamped filenames:

```python
from services.info_lobby_sync.report import list_reports, get_latest_report

# List recent reports
for summary in list_reports(limit=5):
    print(f"{summary['filename']}: {summary['status']}")

# Get latest report
latest = get_latest_report()
print(f"Last sync: {latest.status}, processed: {latest.persistence.total_processed}")
```

Sample report JSON:

```json
{
  "timestamp": "2025-01-15T14:30:00",
  "tenant_code": "CL",
  "status": "ok",
  "fetch": {
    "audiencias_fetched": 1000,
    "viajes_fetched": 50,
    "donativos_fetched": 10,
    "total_fetched": 1060
  },
  "merge": {
    "persons_count": 850,
    "orgs_count": 120,
    "duplicates_found": 45,
    "persons_existing": 500,
    "persons_new": 350
  },
  "persistence": {
    "persons_inserted": 350,
    "persons_updated": 100,
    "orgs_inserted": 80,
    "total_processed": 530
  },
  "duration_seconds": 45.2,
  "errors": []
}
```

## Testing

```bash
# All tests (193 tests)
pytest services/info_lobby_sync/tests/ -v

# By module
pytest services/info_lobby_sync/tests/test_fetcher.py -v
pytest services/info_lobby_sync/tests/test_parser.py -v
pytest services/info_lobby_sync/tests/test_merge.py -v
pytest services/info_lobby_sync/tests/test_persistence.py -v
pytest services/info_lobby_sync/tests/test_report.py -v
pytest services/info_lobby_sync/tests/test_events.py -v
pytest services/info_lobby_sync/tests/test_participation.py -v
```

## Architecture

```
services/info_lobby_sync/
├── __init__.py
├── settings.py          # Pydantic configuration
├── fetcher.py           # SPARQL client and fetch functions
├── parser.py            # JSON → typed dataclasses
├── events.py            # Event extraction for graph (E1.3-S1)
├── participation.py     # Participation edges for graph (E1.3-S2)
├── merge.py             # Deduplication and entity matching
├── persistence.py       # UPSERT to canonical DB tables
├── report.py            # JSON metrics generation
├── queries/             # SPARQL query templates
│   ├── audiencias.sparql
│   ├── viajes.sparql
│   └── donativos.sparql
├── tests/
│   ├── test_fetcher.py
│   ├── test_parser.py
│   ├── test_events.py
│   ├── test_participation.py
│   ├── test_merge.py
│   ├── test_persistence.py
│   └── test_report.py
└── requirements.txt
```

## WAF Notes

The endpoint is behind a Fortinet WAF that requires:
- `Referer: http://datos.infolobby.cl/sparql` header
- Standard browser-like User-Agent

The fetcher handles this automatically.

## Schema Documentation

See [docs/infolobby/sparql-schema.md](../../docs/infolobby/sparql-schema.md) for complete field documentation.
