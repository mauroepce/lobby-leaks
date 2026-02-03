"""
Integration tests for materialized view existence.

These tests verify that the graph materialized views exist and have
the expected structure.

Requires DATABASE_URL environment variable.
"""

import pytest
from sqlalchemy import text


# ============================================================================
# Materialized View Existence Tests
# ============================================================================


@pytest.mark.integration
class TestMvGraphNodesExists:
    """Tests for mv_graph_nodes materialized view existence."""

    def test_mv_graph_nodes_exists(self, engine):
        """Materialized view mv_graph_nodes exists."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM pg_matviews
                WHERE matviewname = 'mv_graph_nodes'
            """))
            count = result.scalar()
            assert count == 1, "mv_graph_nodes materialized view does not exist"

    def test_mv_graph_nodes_has_required_columns(self, engine):
        """mv_graph_nodes has required columns."""
        with engine.connect() as conn:
            # Use pg_attribute for materialized views (not information_schema)
            result = conn.execute(text("""
                SELECT attname
                FROM pg_attribute
                WHERE attrelid = 'mv_graph_nodes'::regclass
                  AND attnum > 0
            """))
            columns = {row[0] for row in result}

        expected = {"node_id", "node_type", "tenant_code", "label"}
        assert expected.issubset(columns), (
            f"Missing columns: {expected - columns}"
        )

    def test_mv_graph_nodes_has_unique_index(self, engine):
        """mv_graph_nodes has unique index for CONCURRENTLY refresh."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'mv_graph_nodes'
                  AND indexdef LIKE '%UNIQUE%'
            """))
            indexes = [row[0] for row in result]

        assert len(indexes) > 0, (
            "mv_graph_nodes has no unique index (required for REFRESH CONCURRENTLY)"
        )

    def test_mv_graph_nodes_is_queryable(self, engine):
        """mv_graph_nodes can be queried."""
        with engine.connect() as conn:
            # Just verify the query runs without error
            result = conn.execute(text("""
                SELECT node_id, node_type, tenant_code, label
                FROM mv_graph_nodes
                LIMIT 1
            """))
            # Fetch to ensure query completes
            list(result)


@pytest.mark.integration
class TestMvGraphLinksExists:
    """Tests for mv_graph_links materialized view existence."""

    def test_mv_graph_links_exists(self, engine):
        """Materialized view mv_graph_links exists."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM pg_matviews
                WHERE matviewname = 'mv_graph_links'
            """))
            count = result.scalar()
            assert count == 1, "mv_graph_links materialized view does not exist"

    def test_mv_graph_links_has_required_columns(self, engine):
        """mv_graph_links has required columns."""
        with engine.connect() as conn:
            # Use pg_attribute for materialized views (not information_schema)
            result = conn.execute(text("""
                SELECT attname
                FROM pg_attribute
                WHERE attrelid = 'mv_graph_links'::regclass
                  AND attnum > 0
            """))
            columns = {row[0] for row in result}

        expected = {"link_id", "source_node_id", "target_node_id", "tenant_code", "label"}
        assert expected.issubset(columns), (
            f"Missing columns: {expected - columns}"
        )

    def test_mv_graph_links_has_unique_index(self, engine):
        """mv_graph_links has unique index for CONCURRENTLY refresh."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'mv_graph_links'
                  AND indexdef LIKE '%UNIQUE%'
            """))
            indexes = [row[0] for row in result]

        assert len(indexes) > 0, (
            "mv_graph_links has no unique index (required for REFRESH CONCURRENTLY)"
        )

    def test_mv_graph_links_is_queryable(self, engine):
        """mv_graph_links can be queried."""
        with engine.connect() as conn:
            # Just verify the query runs without error
            result = conn.execute(text("""
                SELECT link_id, source_node_id, target_node_id, tenant_code, label
                FROM mv_graph_links
                LIMIT 1
            """))
            # Fetch to ensure query completes
            list(result)


@pytest.mark.integration
class TestMvIndexes:
    """Tests for materialized view indexes."""

    def test_mv_graph_nodes_tenant_index_exists(self, engine):
        """mv_graph_nodes has tenant_code index."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'mv_graph_nodes'
                  AND indexname LIKE '%tenant%'
            """))
            indexes = [row[0] for row in result]

        assert len(indexes) > 0, "mv_graph_nodes missing tenant_code index"

    def test_mv_graph_links_source_index_exists(self, engine):
        """mv_graph_links has source_node_id index."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'mv_graph_links'
                  AND indexname LIKE '%source%'
            """))
            indexes = [row[0] for row in result]

        assert len(indexes) > 0, "mv_graph_links missing source_node_id index"

    def test_mv_graph_links_target_index_exists(self, engine):
        """mv_graph_links has target_node_id index."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'mv_graph_links'
                  AND indexname LIKE '%target%'
            """))
            indexes = [row[0] for row in result]

        assert len(indexes) > 0, "mv_graph_links missing target_node_id index"
