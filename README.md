# LobbyLeaks

[![CI](https://github.com/mauroepce/lobby-leaks/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mauroepce/lobby-leaks/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OpenAPI](https://img.shields.io/badge/openapi-validated-brightgreen?logo=openapi)](docs/openapi.yaml)
[![Security Docs](https://img.shields.io/badge/security-docs%20✅-blue)](docs/security/rls.md)

> Global lobbying transparency — first operational module: **Chile** 🇨🇱

A platform for transparent lobbying data aggregation and analysis. Read the [Project Charter](docs/charter.md) for mission, scope, and KPIs.

## Quick Start

**Requirements**: Node 20+, Python 3.12+, Docker

```bash
git clone https://github.com/mauroepce/lobby-leaks.git
cd lobby-leaks

# Setup environment
cp .env.example .env
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
make bootstrap

# Run tests
make quick          # Lint + unit tests + e2e
make test-all       # Complete test suite
make verify         # Full pipeline with DB and RLS tests
```

## Architecture

### Service Template
Reusable boilerplate for creating data ingestion services with production-ready patterns:

- **HTTP Client**: Automatic retries with exponential backoff and jitter
- **Database**: PostgreSQL with SQLAlchemy 2.x and upsert helpers
- **Configuration**: Pydantic Settings with validation
- **Logging**: Structured JSON logging with structlog
- **Testing**: 186 comprehensive tests (unit + integration + database)
- **Docker**: Multi-stage build (187MB image) with security best practices

```bash
# Docker usage
make build-template                           # Build Docker image
docker run --rm --env-file .env \
  lobbyleaks-template --since 2025-01-01     # Run container

# Testing
make template-test              # All tests (186 tests)
make template-test-unit         # Unit tests only (mocked)
make template-test-integration  # Integration tests (real functionality)
```

📖 **Full docs**: [services/_template/README.md](services/_template/README.md)

### Lobby Collector
Microservice for ingesting data from Chile's Ley de Lobby API (audiencias, viajes, donativos):

- **Authentication**: Bearer token with API Key
- **Pagination**: Automatic iteration with AsyncIterator
- **Incremental updates**: Temporal windows (--since, --days)
- **Resilience**: Exponential backoff retries + rate limiting
- **Testing**: 23 comprehensive tests

```bash
# CLI usage
python -m services.lobby_collector.main --days 7          # Last 7 days
python -m services.lobby_collector.main --test-connection # Test API

# Testing
make lobby-collector-test  # Run all 23 tests
```

📖 **Full docs**: [services/lobby_collector/README.md](services/lobby_collector/README.md)

### MCP Hub
Multi-tenant microservice for document processing and OCR (JSON-RPC 2.0 over HTTP).

```bash
make mcp-test-e2e   # Build → DB up → run hub → tests → cleanup
make mcp-curl       # Manual endpoint testing
```

### TypeScript SDK
Auto-generated from OpenAPI spec:

```bash
pnpm run gen-sdk    # Regenerate from docs/openapi.yaml
```

Client available in `clients/ts/` (do not edit manually).

## Development

### Key Commands

| Command | Description |
|---------|-------------|
| `make setup` | Install all dependencies (Node + Python + template) |
| `make lint` | Run ESLint |
| `make test` | Run main tests (excludes RLS) |
| `make test-all` | **All tests** (lint + unit + template + RLS + e2e) |
| `make template-helpers-test` | Test RUT and name normalization helpers |
| `make db-up` | Start PostgreSQL in Docker |
| `make db-reset` | Reset DB with migrations |
| `make verify-clean` | Full pipeline + cleanup |

### Database
PostgreSQL 16 with Row-Level Security (RLS) for multi-tenancy:

```bash
make db-up          # Start Postgres container
make seed           # Apply migrations + seed data
make test-rls       # Run RLS security tests
make psql           # Connect to database
```

## Project Structure

```
lobby-leaks/
├── .github/workflows/     # CI/CD (GitHub Actions with caching)
├── clients/ts/            # TypeScript SDK (auto-generated)
├── docs/                  # Documentation and specs
│   ├── openapi.yaml       # API specification
│   ├── charter.md         # Project mission and KPIs
│   └── security/          # Security documentation
├── prisma/                # Database schema and migrations
├── services/
│   ├── _template/         # Service boilerplate ⭐
│   ├── lobby_collector/   # Ley de Lobby API ingestion
│   └── mcp-hub/           # Document processing microservice
└── tests/                 # Integration and security tests
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening issues or PRs.

## Community

We use [GitHub Discussions](../../discussions) for community interaction:

- **Announcements** – Official updates from maintainers
- **Q&A** – Ask questions and get help
- **Ideas** – Propose features (polls enabled)

👉 [Community Guide](./docs/community.md)

## Security & Contact

- Security issues: **[maintainer@lobbyleaks.com](mailto:maintainer@lobbyleaks.com)**
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](docs/security/rls.md)

## License

MIT License - See [LICENSE](LICENSE) for details.
