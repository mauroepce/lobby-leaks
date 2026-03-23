from __future__ import annotations

import os

# Set dummy DATABASE_URL before importing app (pool created at module level)
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

from app.main import app


class AsyncConnectionCtx:
    """Mock async context manager for pool.connection()."""

    def __init__(self, conn: MagicMock):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_conn():
    """Mock async database connection."""
    conn = MagicMock()
    conn.execute = AsyncMock()
    return conn


@pytest.fixture
def mock_pool(mock_conn):
    """Mock AsyncConnectionPool for unit tests."""
    pool = MagicMock()
    pool.connection.return_value = AsyncConnectionCtx(mock_conn)
    return pool


@pytest_asyncio.fixture
async def client(mock_pool):
    """ASGI test client with mocked DB pool."""
    app.state.pool = mock_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(scope="module")
def database_url() -> str:
    """Real DATABASE_URL for integration tests. Skip if not set."""
    url = os.environ.get("DATABASE_URL")
    if not url or url.startswith("postgresql://dummy"):
        pytest.skip("requires real DATABASE_URL for integration tests")
    return url
