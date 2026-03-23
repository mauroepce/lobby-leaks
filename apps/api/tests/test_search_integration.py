from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg_pool import AsyncConnectionPool


@pytest.mark.integration
@pytest.mark.asyncio
class TestSearchIntegration:
    """Integration tests against a real PostgreSQL database.

    Skipped unless DATABASE_URL is set to a real database.
    """

    @pytest_asyncio.fixture(autouse=True)
    async def setup_real_pool(self):
        """Replace app pool with a real connection pool."""
        db_url = os.environ.get("DATABASE_URL")
        if not db_url or db_url.startswith("postgresql://dummy"):
            pytest.skip("requires real DATABASE_URL")

        from app.main import app

        real_pool = AsyncConnectionPool(db_url, min_size=1, max_size=2)
        async with real_pool:
            app.state.pool = real_pool
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                self.client = c
                yield

    async def test_search_returns_persons(self):
        """Search returns person results from the database."""
        r = await self.client.get(
            "/api/v1/search", params={"q": "a", "tenant": "CL", "limit": 5}
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["results"], list)
        assert isinstance(body["total"], int)

    async def test_search_case_insensitive(self):
        """ILIKE search is case-insensitive."""
        r_upper = await self.client.get(
            "/api/v1/search", params={"q": "JUAN", "tenant": "CL", "limit": 50}
        )
        r_lower = await self.client.get(
            "/api/v1/search", params={"q": "juan", "tenant": "CL", "limit": 50}
        )
        assert r_upper.status_code == 200
        assert r_lower.status_code == 200
        assert r_upper.json()["total"] == r_lower.json()["total"]

    async def test_tenant_isolation(self):
        """Search with a non-existent tenant returns no results."""
        r = await self.client.get(
            "/api/v1/search", params={"q": "a", "tenant": "ZZ", "limit": 5}
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["results"] == []

    async def test_limit_respected(self):
        """Limit parameter caps the number of results."""
        r = await self.client.get(
            "/api/v1/search", params={"q": "a", "tenant": "CL", "limit": 2}
        )
        assert r.status_code == 200
        assert len(r.json()["results"]) <= 2

    async def test_result_has_correct_types(self):
        """Each result has valid type field."""
        r = await self.client.get(
            "/api/v1/search", params={"q": "a", "tenant": "CL", "limit": 10}
        )
        assert r.status_code == 200
        for item in r.json()["results"]:
            assert item["type"] in ("person", "organisation")
            assert "id" in item
            assert "label" in item
