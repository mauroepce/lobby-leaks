# LobbyLeaks Service Template

A reusable boilerplate for creating new LobbyLeaks services with best practices built-in.

> 📖 **Project Documentation**: [Main README](../../README.md) | [Architecture Overview](../../RESUME.md)

## Features

- **🔄 HTTP Client with Retries**: HTTPX-based client with exponential backoff and jitter
- **🗄️ PostgreSQL Database**: SQLAlchemy 2.x with psycopg3 and upsert helpers
- **⚙️ Configuration Management**: Pydantic Settings with .env support and validation
- **📝 Structured Logging**: JSON logging with structlog and stdlib compatibility
- **🖥️ CLI Interface**: Argparse-based command line interface
- **🧪 Testing Ready**: 75 comprehensive tests (unit + integration + database)
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

The template includes **75 comprehensive tests** covering unit testing (with mocks), integration testing (with real functionality), and database testing (with PostgreSQL).

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

# Run template tests as part of complete test suite
make test-all         # lint + unit + template + RLS + MCP e2e (74 tests total)

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
│   └── test_upsert.py          # Database upsert tests (18 tests)
```

### Test Categories

#### 🧪 **Unit Tests** (51 tests - no database required)
- **HTTP Client** (15 tests): Retry logic, backoff calculation, error handling
- **CLI & Main Logic** (25 tests): Argument parsing, date validation, ingestion workflow
- **Database Statement Generation** (11 tests): SQL upsert generation, error handling (mocked)

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

### Docker Usage

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY services/your-service/ services/your-service/

CMD ["python", "-m", "services.your-service.main", "--since", "2025-01-01"]
```

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