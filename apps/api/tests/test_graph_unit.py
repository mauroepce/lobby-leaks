"""Unit tests for GET /api/v1/graph.

DB is mocked end-to-end via the `mock_pool` / `mock_conn` fixtures defined in
conftest.py. These tests exercise:
    - request validation (422 on bad inputs)
    - response shape + status codes (200, 404)
    - truncation flag behaviour
    - depth-1 vs depth-2 branching at the router level

Integration coverage (real DB queries against Neon) lives in
test_graph_integration.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


def _set_center_exists(mock_conn, node_type: str = "person") -> None:
    """First DB call in the router is CENTER_TYPE_SQL — make it return a row."""
    cursor = mock_conn.execute.return_value
    cursor.fetchone = AsyncMock(return_value=(node_type,))


def _set_subgraph_rows(mock_conn, rows: list[tuple]) -> None:
    """Subsequent fetchall() returns the tagged (row_kind, a, b, c, d) rows."""
    cursor = mock_conn.execute.return_value
    cursor.fetchall = AsyncMock(return_value=rows)


@pytest.mark.asyncio
class TestGraphValidation:
    """Request validation — these never reach the DB."""

    async def test_missing_center_returns_422(self, client: AsyncClient):
        r = await client.get("/api/v1/graph", params={"tenant": "CL"})
        assert r.status_code == 422

    async def test_empty_center_returns_422(self, client: AsyncClient):
        r = await client.get("/api/v1/graph", params={"center": "", "tenant": "CL"})
        assert r.status_code == 422

    async def test_depth_out_of_range_returns_422(self, client: AsyncClient):
        r = await client.get(
            "/api/v1/graph",
            params={"center": "abc", "tenant": "CL", "depth": 3},
        )
        assert r.status_code == 422

    async def test_depth_zero_returns_422(self, client: AsyncClient):
        r = await client.get(
            "/api/v1/graph",
            params={"center": "abc", "tenant": "CL", "depth": 0},
        )
        assert r.status_code == 422

    async def test_limit_events_too_high_returns_422(self, client: AsyncClient):
        r = await client.get(
            "/api/v1/graph",
            params={"center": "abc", "tenant": "CL", "limit_events": 300},
        )
        assert r.status_code == 422

    async def test_limit_events_zero_returns_422(self, client: AsyncClient):
        r = await client.get(
            "/api/v1/graph",
            params={"center": "abc", "tenant": "CL", "limit_events": 0},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
class TestGraphResponse:
    """Response shape + 404 behaviour."""

    async def test_unknown_center_returns_404(
        self, client: AsyncClient, mock_conn
    ):
        # CENTER_TYPE_SQL → no row → 404.
        cursor = mock_conn.execute.return_value
        cursor.fetchone = AsyncMock(return_value=None)

        r = await client.get(
            "/api/v1/graph", params={"center": "nope", "tenant": "CL"}
        )
        assert r.status_code == 404
        assert "nope" in r.json()["detail"]

    async def test_empty_subgraph_returns_just_center_node(
        self, client: AsyncClient, mock_conn
    ):
        # Center exists, but has no links — the query still returns the center
        # node via the all_node_ids CTE.
        _set_center_exists(mock_conn, node_type="person")
        _set_subgraph_rows(mock_conn, [
            ("node", "center-id", "person", "juan perez", None),
        ])

        r = await client.get(
            "/api/v1/graph", params={"center": "center-id", "tenant": "CL"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["center"] == "center-id"
        assert body["depth"] == 2  # default
        assert body["truncated"] is False
        assert len(body["nodes"]) == 1
        assert body["nodes"][0] == {"id": "center-id", "type": "person", "label": "juan perez"}
        assert body["links"] == []

    async def test_returns_nodes_and_links_in_shape(
        self, client: AsyncClient, mock_conn
    ):
        _set_center_exists(mock_conn, node_type="person")
        _set_subgraph_rows(mock_conn, [
            ("node", "center-id", "person", "juan perez", None),
            ("node", "event-1", "event", "audiencia-uri-1", None),
            ("node", "co-org-1", "organisation", "empresa sa", None),
            ("link", "link-1", "event-1", "center-id", "PASIVO"),
            ("link", "link-2", "event-1", "co-org-1", "REPRESENTADO"),
        ])

        r = await client.get(
            "/api/v1/graph", params={"center": "center-id", "tenant": "CL"}
        )
        assert r.status_code == 200
        body = r.json()
        assert {n["id"] for n in body["nodes"]} == {"center-id", "event-1", "co-org-1"}
        assert {(l["source"], l["target"], l["label"]) for l in body["links"]} == {
            ("event-1", "center-id", "PASIVO"),
            ("event-1", "co-org-1", "REPRESENTADO"),
        }

    async def test_depth_param_passed_through(
        self, client: AsyncClient, mock_conn
    ):
        # depth=1 should be reflected in the response body even when no links
        # are returned (the body's depth field echoes the request).
        _set_center_exists(mock_conn, node_type="organisation")
        _set_subgraph_rows(mock_conn, [
            ("node", "center-id", "organisation", "fundacion x", None),
        ])

        r = await client.get(
            "/api/v1/graph",
            params={"center": "center-id", "tenant": "CL", "depth": 1},
        )
        assert r.status_code == 200
        assert r.json()["depth"] == 1


@pytest.mark.asyncio
class TestGraphTruncation:
    """The truncated flag fires when direct events hit the limit AND a total
    count is greater than the limit; otherwise it stays False."""

    async def test_truncated_false_when_under_limit(
        self, client: AsyncClient, mock_conn
    ):
        _set_center_exists(mock_conn)
        # 3 direct events returned, default limit_events=50 → not truncated.
        _set_subgraph_rows(mock_conn, [
            ("node", "center-id", "person", "juan", None),
            ("link", "l1", "event-1", "center-id", "PASIVO"),
            ("link", "l2", "event-2", "center-id", "PASIVO"),
            ("link", "l3", "event-3", "center-id", "PASIVO"),
        ])

        r = await client.get(
            "/api/v1/graph", params={"center": "center-id", "tenant": "CL"}
        )
        assert r.status_code == 200
        assert r.json()["truncated"] is False

    async def test_truncated_true_when_total_exceeds_limit(
        self, client: AsyncClient, mock_conn
    ):
        # We call /graph with limit_events=2 and return exactly 2 unique
        # direct-event sources from the subgraph; then the truncation count
        # query returns 50 (total in DB). Router should flag truncated=true.
        _set_center_exists(mock_conn)
        cursor = mock_conn.execute.return_value
        cursor.fetchall = AsyncMock(return_value=[
            ("node", "center-id", "person", "juan", None),
            ("link", "l1", "event-1", "center-id", "PASIVO"),
            ("link", "l2", "event-2", "center-id", "PASIVO"),
        ])
        # First fetchone() is CENTER_TYPE_SQL ("person"); second is the
        # COUNT_DIRECT_EVENTS_SQL (50).
        cursor.fetchone = AsyncMock(side_effect=[("person",), (50,)])

        r = await client.get(
            "/api/v1/graph",
            params={"center": "center-id", "tenant": "CL", "limit_events": 2},
        )
        assert r.status_code == 200
        assert r.json()["truncated"] is True
