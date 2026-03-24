from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTenantResolution:
    """Tests for tenant resolution from query param and/or header."""

    async def test_tenant_from_query_param(self, client: AsyncClient, mock_conn):
        """Query param ?tenant=CL resolves correctly."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=[])
        cursor.fetchone = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=(0,))

        r = await client.get("/api/v1/search", params={"q": "test", "tenant": "CL"})
        assert r.status_code == 200

    async def test_tenant_from_header(self, client: AsyncClient, mock_conn):
        """Header X-Tenant-Id resolves correctly."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=[])
        cursor.fetchone = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=(0,))

        r = await client.get(
            "/api/v1/search",
            params={"q": "test"},
            headers={"X-Tenant-Id": "CL"},
        )
        assert r.status_code == 200

    async def test_tenant_both_same(self, client: AsyncClient, mock_conn):
        """Both param and header present with same value — ok."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=[])
        cursor.fetchone = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=(0,))

        r = await client.get(
            "/api/v1/search",
            params={"q": "test", "tenant": "CL"},
            headers={"X-Tenant-Id": "CL"},
        )
        assert r.status_code == 200

    async def test_tenant_both_differ_returns_400(self, client: AsyncClient):
        """Both param and header present with different values — 400."""
        r = await client.get(
            "/api/v1/search",
            params={"q": "test", "tenant": "CL"},
            headers={"X-Tenant-Id": "UY"},
        )
        assert r.status_code == 400
        assert "Conflicting" in r.json()["detail"]

    async def test_tenant_missing_returns_400(self, client: AsyncClient):
        """No param and no header — 400."""
        r = await client.get("/api/v1/search", params={"q": "test"})
        assert r.status_code == 400
        assert "Missing" in r.json()["detail"]

    async def test_tenant_invalid_format_returns_400(self, client: AsyncClient):
        """Invalid tenant format — 400."""
        for bad in ("CHILE", "1A", "", "C"):
            r = await client.get(
                "/api/v1/search", params={"q": "test", "tenant": bad}
            )
            assert r.status_code == 400, f"Expected 400 for tenant={bad!r}"

    async def test_tenant_lowercase_param_uppercased(self, client: AsyncClient, mock_conn):
        """Lowercase query param is uppercased automatically."""
        cursor = mock_conn.execute.return_value
        cursor.fetchall = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=[])
        cursor.fetchone = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value=(0,))

        r = await client.get("/api/v1/search", params={"q": "test", "tenant": "cl"})
        assert r.status_code == 200
