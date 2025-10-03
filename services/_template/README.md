# LobbyLeaks Service Template

A reusable boilerplate for creating new LobbyLeaks services with best practices built-in.

> 📖 **Project Documentation**: [Main README](../../README.md) | [Architecture Overview](../../RESUME.md)

## Features

- **🔄 HTTP Client with Retries**: HTTPX-based client with exponential backoff and jitter
- **🗄️ PostgreSQL Database**: SQLAlchemy 2.x with psycopg3 and upsert helpers
- **🇨🇱 Data Normalization**: Chilean RUT validation (módulo 11) and name normalization
- **⚙️ Configuration Management**: Pydantic Settings with .env support and validation
- **📝 Structured Logging**: JSON logging with structlog and stdlib compatibility
- **🖥️ CLI Interface**: Argparse-based command line interface
- **🧪 Testing Ready**: 186 comprehensive tests (unit + integration + database + helpers)
- **🔒 Type Safety**: Full type hints and mypy compatibility

## Quick Start

### 1. Copy the Template

```bash
# Copy template to create a new service
cp -r services/_template/ services/your-service-name/

# Update the service name in files
find services/your-service-name/ -type f -name "*.py" -exec sed -i '' 's/_template/your-service-name/g' {} \;
```

### 2. Install Dependencies

Add these dependencies to your service's `requirements.txt`:

```txt
httpx>=0.25.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
structlog>=23.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
sqlalchemy>=2.0.0
psycopg[binary]>=3.1,<4.0
```

### 3. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your service configuration:

```bash
# Required Configuration
API_KEY=your_api_key_here
DB_DSN=postgresql://user:pass@localhost:5432/lobbyleaks

# Optional Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
API_BASE_URL=https://api.example.com
API_TIMEOUT=30.0
API_MAX_RETRIES=3
SERVICE_NAME=your-service-name
ENVIRONMENT=development
```

### 4. Run the Service

```bash
# Basic usage
python -m services.your-service-name.main --since 2025-01-01

# With debug logging
python -m services.your-service-name.main --since 2025-01-01 --log-level DEBUG

# With text format (development)
python -m services.your-service-name.main --since 2025-01-01 --log-format text
```

## Configuration Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `API_KEY` | API key for external service authentication | `sk-abc123...` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `https://api.example.com` | Base URL for the external API |
| `API_TIMEOUT` | `30.0` | API request timeout in seconds |
| `API_MAX_RETRIES` | `3` | Maximum retry attempts for failed requests |
| `DB_DSN` | `None` | PostgreSQL connection string |
| `DB_POOL_SIZE` | `5` | Database connection pool size |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FORMAT` | `json` | Log output format (json, text) |
| `SERVICE_NAME` | `lobbyleaks-service` | Service name for logging |
| `ENVIRONMENT` | `development` | Environment (development, staging, production) |
| `RATE_LIMIT_REQUESTS` | `100` | Maximum requests per minute |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window in seconds |

## Architecture

### Database Module (`db/`)

- **Engine Management**: Production-ready PostgreSQL connections with SQLAlchemy 2.x
- **Connection Pooling**: Automatic connection lifecycle with pre-ping and recycling
- **Upsert Operations**: INSERT ... ON CONFLICT helpers for idempotent operations
- **Multi-conflict Support**: Handle single columns, composite keys, or constraint names

```python
from services.your_service.db import get_engine, upsert
from sqlalchemy import Table, MetaData, Column, Integer, String

# Create engine with optimized defaults
engine = get_engine("postgresql+psycopg://user:pass@localhost:5432/db")

# Define table
metadata = MetaData()
users_table = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(100)),
    Column('email', String(255), unique=True)
)

# Upsert operation
stmt = upsert(
    table=users_table,
    conflict_keys="id",  # or ["col1", "col2"] or "constraint_name"
    payload={"id": 1, "name": "John", "email": "john@example.com"},
    update_cols=["name"]  # Optional: only update specific columns
)

# Execute upsert
with engine.connect() as conn:
    conn.execute(stmt)
    conn.commit()
```

### Data Normalization Helpers (`helpers/`)

Utilities for normalizing and validating Chilean data with pluggable adapter pattern.

#### RUT (Chilean Tax ID) Validation

```python
from services.your_service.helpers import normalize_rut, validate_rut

# Normalize RUT to canonical format
rut = normalize_rut("12.345.678-5")  # Returns: "12345678-5"
rut = normalize_rut("12345678-K")     # Returns: "12345678-K"
rut = normalize_rut("invalid")        # Returns: None

# Validate using Chilean módulo 11 algorithm
is_valid = validate_rut("12.345.678-5")  # Returns: True
is_valid = validate_rut("12.345.678-9")  # Returns: False (wrong DV)

# Use in data processing
for record in api.get_lobby_records():
    clean_rut = normalize_rut(record['rut'])
    if validate_rut(clean_rut):
        # Process valid RUT
        pass
```

#### Name Normalization

```python
from services.your_service.helpers import normalize_name

# Remove honorifics and normalize
name = normalize_name("Sr. JUAN PÉREZ")        # Returns: "Juan Pérez"
name = normalize_name("Dip. María González")   # Returns: "María González"
name = normalize_name("  José  López  ")       # Returns: "José López"

# Handles Chilean-specific characters
name = normalize_name("JOSÉ PEÑALOLÉN")        # Returns: "José Peñalolén"

# Use in data cleaning
for record in api.get_data():
    clean_name = normalize_name(record['nombre'])
    # Now consistent for storage and search
```

**Supported Honorifics:** sr/sra/srta, dr/dra, prof, ing, abog, dip/diputado, sen/senador, ministro, alcalde, concejal

**Future:** Pluggable adapter allows integrating external libraries like `python-rut` without code changes.

### HTTP Client (`client.py`)

- **Automatic Retries**: Retries on 5xx status codes and connection timeouts
- **Exponential Backoff**: Base delay 0.5s, doubles each attempt, max 60s
- **Jitter**: Adds 0-20% random delay to prevent thundering herd
- **Structured Logging**: All requests and retries are logged with context

```python
from services.your_service.client import HTTPClient, get_json

# Using the client directly
with HTTPClient(max_retries=5, timeout=60.0) as client:
    data = client.get_json("https://api.example.com/data")

# Convenience function for simple calls
data = get_json("https://api.example.com/data", headers={"Authorization": "Bearer token"})
```

### Configuration (`settings.py`)

- **Environment Variables**: Automatic loading from `.env` and environment
- **Validation**: Type checking and custom validators
- **Caching**: Settings are cached to avoid re-reading files

```python
from services.your_service.settings import settings

config = settings()
print(config.api_key)  # Loads from API_KEY env var
print(config.is_production())  # Helper methods available
```

### Logging (`logging.py`)

- **JSON Output**: Structured logs in production
- **Text Output**: Human-readable logs in development
- **Stdlib Compatible**: Works with existing Python logging
- **Contextual**: Request IDs, service metadata automatically included

```python
from services.your_service.logging import get_logger, log_api_call

logger = get_logger(__name__)

# Structured logging
logger.info("Processing batch", batch_id="batch_123", items=100)

# Specialized logging functions
log_api_call(logger, "GET", "https://api.example.com", status_code=200, duration_ms=150.5)
```

### CLI Interface (`main.py`)

- **Argument Parsing**: Handles date parsing and validation
- **Error Handling**: Graceful error handling with proper exit codes
- **Logging Integration**: CLI arguments can override log configuration

```python
# Main ingestion function - customize this for your service
async def ingest_since(since_date: str) -> bool:
    # Your service logic here
    return True
```

## Customization Guide

### 1. Update Service Logic

Edit `main.py` to implement your specific data ingestion logic:

```python
async def fetch_data_since(since_date: date) -> dict:
    # Replace with your API endpoint and logic
    config = settings()
    url = f"{config.api_base_url}/your-endpoint"
    # ... your implementation
```

### 2. Add Custom Configuration

Add service-specific settings to `settings.py`:

```python
class Settings(BaseSettings):
    # Add your custom fields
    custom_api_endpoint: str = Field(description="Custom endpoint path")
    batch_size: int = Field(default=100, description="Processing batch size")
```

### 3. Add Custom Validators

```python
@field_validator("custom_field")
@classmethod
def validate_custom_field(cls, v):
    # Your validation logic
    return v
```

### 4. Extend HTTP Client

Add service-specific methods to the HTTP client:

```python
class CustomHTTPClient(HTTPClient):
    def get_paginated_data(self, url: str, **kwargs):
        # Your pagination logic
        pass
```

## Testing

The template includes **186 comprehensive tests** covering unit testing (with mocks), integration testing (with real functionality), database testing (with PostgreSQL), and data normalization helpers.

### Running Tests

```bash
# All tests (recommended)
make template-test

# Only unit tests (fast, mocked dependencies)
make template-test-unit

# Only integration tests (real functionality)
make template-test-integration

# Only database tests (requires PostgreSQL)
make template-db-test

# Only helpers tests (RUT + name normalization)
make template-helpers-test

# Run template tests as part of complete test suite
make test-all         # lint + unit + template + RLS + MCP e2e (197 tests total)

# Specific test files
python -m pytest services/_template/tests/test_client.py -v
python -m pytest services/_template/tests/test_integration.py -v

# With coverage
python -m pytest services/_template/tests/ --cov=services._template
```

### Test Structure

```
services/_template/
├── tests/
│   ├── __init__.py
│   ├── test_client.py          # HTTP client unit tests (15 tests)
│   ├── test_main.py            # CLI and main logic tests (25 tests)
│   ├── test_integration.py     # Real functionality tests (17 tests)
│   ├── test_upsert.py          # Database upsert tests (18 tests)
│   ├── test_rut.py             # RUT normalization/validation tests (52 tests)
│   └── test_name.py            # Name normalization tests (59 tests)
```

### Test Categories

#### 🧪 **Unit Tests** (162 tests - no database required)
- **HTTP Client** (15 tests): Retry logic, backoff calculation, error handling
- **CLI & Main Logic** (25 tests): Argument parsing, date validation, ingestion workflow
- **Database Statement Generation** (11 tests): SQL upsert generation, error handling (mocked)
- **RUT Normalization/Validation** (52 tests): Chilean RUT módulo 11, formats, edge cases
- **Name Normalization** (59 tests): Honorific removal, unicode, Chilean names

#### 🔗 **Integration Tests** (24 tests - require PostgreSQL)
- **Real Functionality** (17 tests): Configuration loading, CLI subprocess, HTTP client initialization
- **Database Operations** (7 tests): Real PostgreSQL upsert, insert, update, conflict resolution, idempotency

### Writing Tests

Example test with mocked HTTP client:

```python
import pytest
from unittest.mock import Mock, patch
from services._template.client import HTTPClient

@patch('httpx.Client')
def test_client_retry_on_500(mock_client):
    # Mock setup
    mock_response = Mock()
    mock_response.status_code = 500
    mock_client.return_value.request.return_value = mock_response

    # Test retry behavior
    client = HTTPClient(max_retries=3)
    with pytest.raises(RetryableHTTPError):
        client.get("https://example.com")

    # Verify retries happened
    assert mock_client.return_value.request.call_count == 4  # 1 + 3 retries
```

Example database test:

```python
import pytest
from sqlalchemy import MetaData, Table, Column, Integer, String
from services._template.db import get_engine, upsert

@pytest.mark.db
class TestDatabaseOperations:
    @pytest.fixture
    def engine(self):
        dsn = "postgresql+psycopg://user:pass@localhost:5432/testdb"
        return get_engine(dsn)

    @pytest.fixture
    def test_table(self, engine):
        metadata = MetaData()
        table = Table('test_users', metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(100))
        )
        metadata.create_all(bind=engine)
        yield table
        metadata.drop_all(bind=engine)

    def test_upsert_creates_new_record(self, engine, test_table):
        stmt = upsert(test_table, "id", {"id": 1, "name": "John"})

        with engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

            # Verify record exists
            result = conn.execute(select(test_table)).fetchone()
            assert result.name == "John"
```

## Docker Deployment

The template includes a production-ready multi-stage Dockerfile optimized for size and security.

### Building the Image

```bash
# Build from the template directory
cd services/_template
docker build -t lobbyleaks-template .

# Or build from project root
docker build -t lobbyleaks-template -f services/_template/Dockerfile services/_template

# Build with custom tag
docker build -t my-service:v1.0.0 services/_template
```

### Running the Container

#### Basic Usage

```bash
# Show help
docker run --rm lobbyleaks-template

# Run with arguments
docker run --rm \
  --env-file .env \
  lobbyleaks-template --since 2025-01-01

# With debug logging
docker run --rm \
  --env-file .env \
  lobbyleaks-template --since 2025-01-01 --log-level DEBUG
```

#### With Database Connection

When connecting to a PostgreSQL database, you need proper networking:

```bash
# Option 1: Connect to host database (development)
docker run --rm \
  --network host \
  -e DB_DSN="postgresql://user:pass@localhost:5432/lobbyleaks" \
  -e API_KEY="your_api_key" \
  lobbyleaks-template --since 2025-01-01

# Option 2: Connect to database in Docker network
docker run --rm \
  --network lobby-leaks_default \
  -e DB_DSN="postgresql://lobbyleaks:l0bby@db:5432/lobbyleaks" \
  -e API_KEY="your_api_key" \
  lobbyleaks-template --since 2025-01-01

# Option 3: Using docker-compose (recommended for production)
# See docker-compose.yml example below
```

#### Environment Variables

```bash
# Pass individual environment variables
docker run --rm \
  -e API_KEY="sk-abc123" \
  -e DB_DSN="postgresql://user:pass@localhost:5432/db" \
  -e LOG_LEVEL="DEBUG" \
  lobbyleaks-template --since 2025-01-01

# Or use an env file
docker run --rm --env-file .env lobbyleaks-template --since 2025-01-01
```

### Docker Compose Integration

Create a `docker-compose.yml` for your service:

```yaml
version: '3.8'

services:
  your-service:
    build: ./services/_template
    image: lobbyleaks-template:latest
    container_name: lobbyleaks-service
    environment:
      - API_KEY=${API_KEY}
      - DB_DSN=postgresql://lobbyleaks:l0bby@db:5432/lobbyleaks
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
      - ENVIRONMENT=production
    networks:
      - lobby-leaks_default
    depends_on:
      db:
        condition: service_healthy
    command: ["--since", "2025-01-01"]

  db:
    image: postgres:16
    environment:
      - POSTGRES_USER=lobbyleaks
      - POSTGRES_PASSWORD=l0bby
      - POSTGRES_DB=lobbyleaks
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "lobbyleaks"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - lobby-leaks_default

networks:
  lobby-leaks_default:
    external: true
```

Run with docker-compose:

```bash
docker-compose up your-service
```

### Dockerfile Architecture

The template uses a **multi-stage build** for optimal image size and security:

#### Stage 1: Builder
- Compiles Python packages with C extensions (psycopg, etc.)
- Installs build tools (gcc, g++, libpq-dev)
- Creates wheels for all dependencies

#### Stage 2: Runtime
- Minimal base image with only runtime dependencies
- Non-root user (`appuser`) for security
- Copies only compiled packages (no build tools)
- Includes health check for container orchestration

**Image Size**: ~200MB (vs ~500MB without multi-stage)

### Makefile Shortcuts

Use the root Makefile for convenient Docker operations:

```bash
# Build template image
make build-template

# Run template container
make run-template

# Complete setup (install all deps)
make setup
```

## Production Deployment

### Environment Configuration

```bash
# Production environment variables
API_KEY=your_production_api_key
DB_DSN=postgresql://user:pass@prod-db:5432/lobbyleaks
LOG_LEVEL=INFO
LOG_FORMAT=json
ENVIRONMENT=production
API_TIMEOUT=60.0
API_MAX_RETRIES=5
```

### Security Considerations

1. **Non-root User**: Container runs as `appuser` (not root)
2. **No Secrets in Image**: Use `--env-file` or orchestrator secrets
3. **Minimal Base**: `python:3.12-slim` reduces attack surface
4. **Health Checks**: Built-in health check for orchestration
5. **.dockerignore**: Prevents copying sensitive files (.env, .git, tests)

### Monitoring

The service logs structured JSON that can be easily parsed by log aggregators:

```json
{
  "event": "api_call",
  "method": "GET",
  "url": "https://api.example.com/data",
  "status_code": 200,
  "duration_ms": 150.5,
  "timestamp": "2025-01-01T12:00:00Z",
  "service": "your-service-name",
  "environment": "production"
}
```

## Integration with LobbyLeaks

### Database Integration

```python
# Add database operations
from prisma import Prisma

async def save_records(records: list):
    db = Prisma()
    await db.connect()

    try:
        for record in records:
            await db.fundingrecord.create(data=record)
    finally:
        await db.disconnect()
```

### MCP Hub Integration

```python
# Call MCP Hub for document processing
from services._template.client import get_json

async def process_document(doc_url: str):
    response = get_json("http://mcp-hub:8000/rpc2", json={
        "method": "ocr_pdf",
        "params": {"url": doc_url}
    })
    return response
```

## Contributing

When extending this template:

1. **Maintain Type Safety**: Use type hints throughout
2. **Add Tests**: Cover new functionality with tests
3. **Update Documentation**: Keep README.md current
4. **Follow Conventions**: Use existing patterns for consistency
5. **Log Structured Data**: Use the logging utilities for consistency

## License

MIT License - See [LICENSE](../../LICENSE) for details.

---

*Template Version: 0.1.0*
*Last Updated: September 2025*