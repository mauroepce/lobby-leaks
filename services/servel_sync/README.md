# SERVEL Sync Service

Fetches, parses, matches, and persists campaign financing data from Chile's SERVEL (Servicio Electoral).

## Overview

This service handles the complete SERVEL donation pipeline:
- **Data Acquisition** (S1): Loading CSV/Excel files from local paths or remote URLs
- **Parsing** (S1): Converting raw records into typed `ParsedDonation` objects
- **Normalization** (S1): Standardizing names, RUTs, dates, and amounts for matching
- **Merge** (S2): Deterministic matching against canonical entities (Person/Organisation)
- **Orchestration** (S3): Coordinating the pipeline with DB lookups
- **Persistence** (S4): Storing donation events and edges in the graph

## Modules

### `fetcher.py`
Data acquisition from files and URLs.

```python
from services.servel_sync.fetcher import fetch, fetch_from_file, fetch_from_url

# Auto-detect source type
records = fetch("data/servel/donations_2021.csv")
records = fetch("https://example.com/donations.xlsx")

# Explicit methods
records = fetch_from_file("local_file.csv", encoding="latin-1")
records = fetch_from_url("https://example.com/data.csv", timeout=30.0)
```

Features:
- CSV and Excel (.xlsx/.xls) support
- Encoding fallback (UTF-8 → Latin-1 → CP1252)
- Configurable retries and timeouts for URLs
- Returns `List[Dict[str, Any]]`

### `parser.py`
Parsing and normalization of donation records.

```python
from services.servel_sync.parser import parse_donation, parse_all_donations

# Parse single record
donation = parse_donation({
    "NOMBRE_DONANTE": "JUAN PÉREZ",
    "NOMBRE_CANDIDATO": "MARÍA GARCÍA",
    "MONTO": "1.000.000",
    "AÑO_ELECCION": "2021"
})

print(donation.donor_name_normalized)  # "juan perez"
print(donation.amount_clp)  # 1000000

# Parse multiple records
donations, errors = parse_all_donations(records, skip_errors=True)
```

#### ParsedDonation Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `donor_name` | str | ✓ | Original donor name |
| `donor_name_normalized` | str | ✓ | Normalized for matching |
| `candidate_name` | str | ✓ | Original candidate name |
| `candidate_name_normalized` | str | ✓ | Normalized for matching |
| `amount_clp` | int | ✓ | Amount in CLP (integer) |
| `campaign_year` | int | ✓ | Election year |
| `donor_rut` | str | | Normalized RUT |
| `donor_rut_valid` | bool | | RUT validation result |
| `candidate_rut` | str | | Normalized RUT |
| `candidate_rut_valid` | bool | | RUT validation result |
| `donation_date` | date | | Donation date |
| `election_type` | str | | Type of election |
| `candidate_party` | str | | Political party |
| `donor_type` | str | | Type of donor |
| `region` | str | | Geographic region |
| `checksum` | str | | SHA256 for change detection |

#### Column Aliases

The parser supports multiple column name variations commonly found in SERVEL datasets:

- **donor_name**: `NOMBRE_DONANTE`, `DONANTE`, `NOMBRE_APORTANTE`, `APORTANTE`
- **donor_rut**: `RUT_DONANTE`, `RUT_APORTANTE`
- **candidate_name**: `NOMBRE_CANDIDATO`, `CANDIDATO`, `NOMBRE_BENEFICIARIO`
- **amount_clp**: `MONTO`, `MONTO_APORTE`, `VALOR`, `MONTO_CLP`
- **campaign_year**: `AÑO_ELECCION`, `ANIO_ELECCION`, `AÑO`, `PERIODO`
- **donation_date**: `FECHA`, `FECHA_APORTE`, `FECHA_DONACION`

All aliases also accept lowercase variants.

#### Normalization Rules

**Name Normalization:**
- Lowercase
- Remove accents (NFD decomposition)
- Remove punctuation
- Collapse whitespace

**Amount Parsing:**
- Handles Chilean format: `1.234.567` (dots as thousand separators)
- Handles mixed format: `1.234,56`
- Removes currency symbols ($)
- Rounds decimals to integer

**Date Parsing:**
- ISO: `2021-03-15`
- Chilean: `15-03-2021`, `15/03/2021`
- European: `15.03.2021`
- Year only: `2021` → January 1st

### `merge.py`
Deterministic matching of donations against canonical entities.

```python
from services.servel_sync.merge import merge_donations

result = merge_donations(
    donations,
    persons_by_rut={"12345678-9": "uuid-1"},
    persons_by_name={"juan perez": ["uuid-2"]},
    orgs_by_rut={},
    orgs_by_name={},
)

print(f"Matched by RUT: {result.donors_matched_by_rut}")
print(f"Matched by name: {result.donors_matched_by_name}")
```

**Matching Rules:**
1. **RUT** (priority) - deterministic match
2. **Normalized name** (fallback) - only if unique match
3. **Collision** (>1 match) - skip, no merge

### `loaders.py`
Load canonical entities from PostgreSQL into lookup dictionaries.

```python
from services.servel_sync.loaders import load_person_lookups, load_org_lookups

with engine.connect() as conn:
    persons_by_rut, persons_by_name = load_person_lookups(conn, "CL")
    orgs_by_rut, orgs_by_name = load_org_lookups(conn, "CL")
```

### `orchestrator.py`
Coordinate the complete pipeline.

```python
from services.servel_sync.orchestrator import run_servel_donation_sync

result = run_servel_donation_sync(
    "data/servel/donations_2021.csv",
    engine,
    "CL",
)

print(f"Total: {result.total_records}")
print(f"Matched: {result.donors_matched_by_rut + result.donors_matched_by_name}")
```

### `donation_persistence.py`
Persist merged donations as Events and Edges in the graph.

```python
from services.servel_sync.donation_persistence import persist_donation_events

result = persist_donation_events(merge_result, engine, "CL")

print(f"Events created: {result.events_created}")
print(f"Donor edges: {result.donor_edges_created}")
print(f"Candidate edges: {result.candidate_edges_created}")
```

**Persistence Rules:**
- Event created ONLY if `candidate_person_id` exists
- Donor edge is optional (created if donor matched)
- Candidate edge is mandatory
- Uses UPSERT for idempotency
- `externalId`: `SERVEL:{checksum}`
- Edge labels: `DONANTE`, `DONATARIO`

### `settings.py`
Configuration via environment variables.

| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_SERVEL_SYNC` | `true` | Enable/disable service |
| `HTTP_TIMEOUT` | `60.0` | URL fetch timeout (seconds) |
| `HTTP_MAX_RETRIES` | `3` | Maximum retry attempts |
| `DATA_DIR` | `data/servel` | Data storage directory |
| `DATABASE_URL` | | PostgreSQL connection string |
| `LOG_LEVEL` | `INFO` | Logging level |

## Tests

```bash
# Run all servel_sync tests
pytest services/servel_sync/tests/ -v

# Run specific test module
pytest services/servel_sync/tests/test_parser.py -v
pytest services/servel_sync/tests/test_fetcher.py -v
pytest services/servel_sync/tests/test_merge.py -v
pytest services/servel_sync/tests/test_loaders.py -v
pytest services/servel_sync/tests/test_orchestrator.py -v
pytest services/servel_sync/tests/test_donation_persistence.py -v
```

**Test Coverage:**
- `test_fetcher.py`: 19 tests (CSV/Excel, URL, retries)
- `test_parser.py`: 56 tests (normalization, parsing, aliases)
- `test_merge.py`: 30 tests (RUT/name matching, collisions)
- `test_loaders.py`: 18 tests (DB lookups, validation)
- `test_orchestrator.py`: 11 tests (pipeline coordination)
- `test_donation_persistence.py`: 25+ tests (events, edges, idempotency)

## Architecture

```
services/servel_sync/
├── __init__.py
├── settings.py              # Pydantic configuration
├── fetcher.py               # S1: Data acquisition (CSV/Excel, file/URL)
├── parser.py                # S1: ParsedDonation dataclass & normalization
├── merge.py                 # S2: Deterministic matching logic
├── loaders.py               # S3: Load entities from PostgreSQL
├── orchestrator.py          # S3: Pipeline coordination
├── donation_persistence.py  # S4: Persist events & edges
├── README.md
└── tests/
    ├── __init__.py
    ├── test_fetcher.py
    ├── test_parser.py
    ├── test_merge.py
    ├── test_loaders.py
    ├── test_orchestrator.py
    └── test_donation_persistence.py
```

## Pipeline Flow

```
┌─────────────┐    ┌──────────┐    ┌───────────┐    ┌──────────────┐
│  fetcher.py │ -> │ parser.py│ -> │ merge.py  │ -> │ persistence  │
│   (S1)      │    │   (S1)   │    │   (S2)    │    │    (S4)      │
└─────────────┘    └──────────┘    └───────────┘    └──────────────┘
                                         ↑
                                   ┌───────────┐
                                   │ loaders.py│
                                   │   (S3)    │
                                   └───────────┘
```

## Dependencies

- `pandas` - DataFrame operations
- `openpyxl` - Excel file support
- `httpx` - HTTP client for URL fetching
- `pydantic-settings` - Configuration management
- `sqlalchemy` - Database operations

RUT utilities are imported from `services._template.helpers.rut`.
