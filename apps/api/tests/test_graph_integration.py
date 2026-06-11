"""Integration tests for GET /api/v1/graph against a real DB.

Skipped unless DATABASE_URL points at a real Postgres with the canonical
schema + MVs populated. The fixture finds a real center entity (the
person/org with the most incoming links in `mv_graph_links` for tenant CL)
so the tests exercise non-trivial subgraphs.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg_pool import AsyncConnectionPool


@pytest.mark.integration
@pytest.mark.asyncio
class TestGraphIntegration:

    @pytest_asyncio.fixture(autouse=True)
    async def setup_real_pool(self):
        db_url = os.environ.get("DATABASE_URL")
        if not db_url or db_url.startswith("postgresql://dummy"):
            pytest.skip("requires real DATABASE_URL")

        from app.main import app

        pool = AsyncConnectionPool(db_url, min_size=1, max_size=2)
        async with pool:
            app.state.pool = pool
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                self.client = c
                self.pool = pool
                # Pick a real center: the entity with the MOST incoming links.
                # That guarantees the depth-2 fanout in the response.
                async with pool.connection() as conn:
                    cursor = await conn.execute("""
                        SELECT target_node_id, count(*) AS c
                        FROM mv_graph_links
                        WHERE tenant_code = 'CL'
                        GROUP BY target_node_id
                        ORDER BY c DESC
                        LIMIT 1
                    """)
                    row = await cursor.fetchone()
                    if not row:
                        pytest.skip("no graph links for tenant CL — load data first")
                    self.center_id = row[0]
                yield

    async def test_returns_center_node_in_response(self):
        r = await self.client.get(
            "/api/v1/graph",
            params={"center": self.center_id, "tenant": "CL", "limit_events": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["center"] == self.center_id
        node_ids = {n["id"] for n in body["nodes"]}
        assert self.center_id in node_ids, "center node must be present in the response"

    async def test_all_links_point_to_returned_nodes(self):
        # Graph invariant: every link's source and target must appear as a
        # node in the same response. The frontend depends on this for
        # rendering (Cosmograph won't draw orphan links).
        r = await self.client.get(
            "/api/v1/graph",
            params={"center": self.center_id, "tenant": "CL", "limit_events": 5},
        )
        body = r.json()
        node_ids = {n["id"] for n in body["nodes"]}
        for link in body["links"]:
            assert link["source"] in node_ids, f"link source {link['source']} missing from nodes"
            assert link["target"] in node_ids, f"link target {link['target']} missing from nodes"

    async def test_link_sources_are_events(self):
        # Event-centric invariant: every link's source MUST be an event node.
        r = await self.client.get(
            "/api/v1/graph",
            params={"center": self.center_id, "tenant": "CL", "limit_events": 5},
        )
        body = r.json()
        nodes_by_id = {n["id"]: n for n in body["nodes"]}
        for link in body["links"]:
            assert nodes_by_id[link["source"]]["type"] == "event", \
                f"link source {link['source']} is not an event node"

    async def test_link_labels_are_valid_roles(self):
        r = await self.client.get(
            "/api/v1/graph",
            params={"center": self.center_id, "tenant": "CL", "limit_events": 5},
        )
        body = r.json()
        valid_roles = {"PASIVO", "ACTIVO", "REPRESENTADO", "FINANCIADOR", "DONANTE"}
        for link in body["links"]:
            assert link["label"] in valid_roles, f"unexpected role label {link['label']!r}"

    async def test_depth_1_returns_fewer_nodes_than_depth_2(self):
        # Depth-2 includes the co-participants in the same events, so it
        # should never be smaller than depth-1 for a non-trivial center.
        r1 = await self.client.get(
            "/api/v1/graph",
            params={
                "center": self.center_id, "tenant": "CL",
                "depth": 1, "limit_events": 5,
            },
        )
        r2 = await self.client.get(
            "/api/v1/graph",
            params={
                "center": self.center_id, "tenant": "CL",
                "depth": 2, "limit_events": 5,
            },
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        n1 = len(r1.json()["nodes"])
        n2 = len(r2.json()["nodes"])
        assert n2 >= n1, f"depth-2 had {n2} nodes vs depth-1 with {n1}"

    async def test_unknown_center_returns_404(self):
        r = await self.client.get(
            "/api/v1/graph",
            params={"center": "00000000-0000-0000-0000-000000000000", "tenant": "CL"},
        )
        assert r.status_code == 404

    async def test_truncated_flag_fires_with_tiny_limit(self):
        # With limit_events=1 and a hot center, truncated must be True.
        r = await self.client.get(
            "/api/v1/graph",
            params={"center": self.center_id, "tenant": "CL", "limit_events": 1},
        )
        assert r.status_code == 200
        body = r.json()
        # The "most-linked" center has more than 1 incoming event by
        # construction (it was picked to maximize link count).
        assert body["truncated"] is True
