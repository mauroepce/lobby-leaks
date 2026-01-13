# SERVEL Sync Service

Fetches and parses campaign financing data from Chile's SERVEL (Servicio Electoral).

## Overview

This service handles:
- **Data Acquisition**: Loading CSV/Excel files from local paths or remote URLs
- **Parsing**: Converting raw records into typed `ParsedDonation` objects
- **Normalization**: Standardizing names, RUTs, dates, and amounts for matching

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
```

**Test Coverage:**
- 75 tests covering fetcher and parser functionality
- Column alias mapping
- Amount/date parsing edge cases
- Encoding fallback behavior
- URL retry logic

## Architecture

```
services/servel_sync/
├── __init__.py
├── settings.py          # Pydantic configuration
├── fetcher.py           # Data acquisition (CSV/Excel, file/URL)
├── parser.py            # ParsedDonation dataclass & normalization
├── README.md
└── tests/
    ├── __init__.py
    ├── test_fetcher.py  # 19 tests
    └── test_parser.py   # 56 tests
```

## Dependencies

- `pandas` - DataFrame operations
- `openpyxl` - Excel file support
- `httpx` - HTTP client for URL fetching
- `pydantic-settings` - Configuration management

RUT utilities are imported from `services._template.helpers.rut`.
