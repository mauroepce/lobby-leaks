from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSearchValidation:
    """Tests for request validation."""

    async def test_missing_q_returns_422(self, client: AsyncClient):
        """Missing q parameter returns 422."""
        r = await client.get("/api/v1/search", params={"tenant": "CL"})
        assert r.status_code == 422

    async def test_empty_q_returns_422(self, client: AsyncClient):
        """Empty q parameter returns 422 (min_length=1)."""
        r = await client.get("/api/v1/search", params={"q": "", "tenant": "CL"})
        assert r.status_code == 422

    async def test_limit_exceeds_max_returns_422(self, client: AsyncClient):
        """Limit > 100 returns 422."""
        r = await client.get(
            "/api/v1/search", params={"q": "test", "tenant": "CL", "limit": 200}
        )
        assert r.status_code == 422

    async def test_limit_zero_returns_422(self, client: AsyncClient):
        """Limit 0 returns 422 (ge=1)."""
        r = await client.get(
            "/api/v1/search", params={"q": "test", "tenant": "CL", "limit": 0}
        )
        assert r.status_code == 422


@pytest.mark.asyncio
class TestSearchResults:
    """Tests for search response shape and behavior."""

    async def test_returns_expected_shape(self, client: AsyncClient, mock_conn):
        """Valid search returns {results: [...], total: N}."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[
            ("uuid-1", "person", "juan perez", "12345678-5"),
            ("uuid-2", "organisation", "empresa sa", "76543210-K"),
        ])
        cursor.fetchone = AsyncMock(return_value=(2,))

        r = await client.get("/api/v1/search", params={"q": "test", "tenant": "CL"})
        assert r.status_code == 200

        body = r.json()
        assert "results" in body
        assert "total" in body
        assert body["total"] == 2
        assert len(body["results"]) == 2

        person = body["results"][0]
        assert person["id"] == "uuid-1"
        assert person["type"] == "person"
        assert person["label"] == "juan perez"
        assert person["rut"] == "12345678-5"

        org = body["results"][1]
        assert org["type"] == "organisation"

    async def test_rut_can_be_null(self, client: AsyncClient, mock_conn):
        """Results with null rut are valid."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[
            ("uuid-1", "person", "sin rut", None),
        ])
        cursor.fetchone = AsyncMock(return_value=(1,))

        r = await client.get("/api/v1/search", params={"q": "sin", "tenant": "CL"})
        assert r.status_code == 200
        assert r.json()["results"][0]["rut"] is None

    async def test_empty_results(self, client: AsyncClient, mock_conn):
        """No matches returns empty list and total 0."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[])
        cursor.fetchone = AsyncMock(return_value=(0,))

        r = await client.get(
            "/api/v1/search", params={"q": "nonexistent", "tenant": "CL"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["results"] == []
        assert body["total"] == 0

    async def test_default_limit_is_20(self, client: AsyncClient, mock_conn):
        """Default limit is 20 when not specified."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[])
        cursor.fetchone = AsyncMock(return_value=(0,))

        await client.get("/api/v1/search", params={"q": "test", "tenant": "CL"})

        # Check the SQL was called with limit=20
        call_args = mock_conn.execute.call_args_list[0]
        params = call_args[0][1]
        assert params["limit"] == 20

    async def test_custom_limit(self, client: AsyncClient, mock_conn):
        """Custom limit is passed to the query."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[])
        cursor.fetchone = AsyncMock(return_value=(0,))

        await client.get(
            "/api/v1/search", params={"q": "test", "tenant": "CL", "limit": 5}
        )

        call_args = mock_conn.execute.call_args_list[0]
        params = call_args[0][1]
        assert params["limit"] == 5

    async def test_tenant_passed_to_query(self, client: AsyncClient, mock_conn):
        """Tenant code is passed to the SQL query."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[])
        cursor.fetchone = AsyncMock(return_value=(0,))

        await client.get("/api/v1/search", params={"q": "test", "tenant": "CL"})

        call_args = mock_conn.execute.call_args_list[0]
        params = call_args[0][1]
        assert params["tenant"] == "CL"

    async def test_pattern_includes_wildcards(self, client: AsyncClient, mock_conn):
        """Search pattern wraps query with % wildcards for ILIKE."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[])
        cursor.fetchone = AsyncMock(return_value=(0,))

        await client.get("/api/v1/search", params={"q": "juan", "tenant": "CL"})

        call_args = mock_conn.execute.call_args_list[0]
        params = call_args[0][1]
        assert params["pattern"] == "%juan%"
