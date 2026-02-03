"""
Refresh materialized views for graph visualization.

This module provides functionality to refresh the mv_graph_nodes and mv_graph_links
materialized views, which power the graph visualization UI.

Usage:
    # Programmatic usage
    from services.graph_refresh import refresh_graph_views
    result = refresh_graph_views(engine, concurrent=True)

    # CLI usage
    python -m services.graph_refresh.refresh_graph

Features:
    - Refreshes mv_graph_nodes and mv_graph_links
    - Supports REFRESH CONCURRENTLY for online operation
    - Returns detailed metrics in RefreshResult
    - Handles errors gracefully
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    """Result of graph view refresh operation with metrics."""

    nodes_count: int = 0
    links_count: int = 0
    duration_seconds: float = 0.0
    concurrent_refresh: bool = False
    refreshed_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

    # Optional detailed metrics (nice-to-have)
    nodes_by_type: Dict[str, int] = field(default_factory=dict)
    links_by_label: Dict[str, int] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if refresh completed without errors."""
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "nodes_count": self.nodes_count,
            "links_count": self.links_count,
            "duration_seconds": self.duration_seconds,
            "concurrent_refresh": self.concurrent_refresh,
            "refreshed_at": self.refreshed_at.isoformat() if self.refreshed_at else None,
            "errors": self.errors,
            "success": self.success,
            "nodes_by_type": self.nodes_by_type,
            "links_by_label": self.links_by_label,
        }


def _refresh_materialized_view(
    conn,
    view_name: str,
    concurrent: bool = False,
) -> None:
    """
    Refresh a single materialized view.

    Args:
        conn: Database connection
        view_name: Name of the materialized view
        concurrent: If True, use REFRESH CONCURRENTLY (requires unique index)
    """
    if concurrent:
        query = text(f'REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}')
    else:
        query = text(f'REFRESH MATERIALIZED VIEW {view_name}')

    conn.execute(query)


def _get_node_counts(conn) -> tuple[int, Dict[str, int]]:
    """
    Get total node count and breakdown by type.

    Returns:
        Tuple of (total_count, counts_by_type)
    """
    query = text("""
        SELECT node_type, COUNT(*) as cnt
        FROM mv_graph_nodes
        GROUP BY node_type
    """)

    result = conn.execute(query)
    counts_by_type: Dict[str, int] = {}
    total = 0

    for row in result:
        if hasattr(row, '_mapping'):
            node_type = row._mapping['node_type']
            cnt = row._mapping['cnt']
        else:
            node_type = row[0]
            cnt = row[1]

        counts_by_type[node_type] = cnt
        total += cnt

    return total, counts_by_type


def _get_link_counts(conn) -> tuple[int, Dict[str, int]]:
    """
    Get total link count and breakdown by label.

    Returns:
        Tuple of (total_count, counts_by_label)
    """
    query = text("""
        SELECT label, COUNT(*) as cnt
        FROM mv_graph_links
        GROUP BY label
    """)

    result = conn.execute(query)
    counts_by_label: Dict[str, int] = {}
    total = 0

    for row in result:
        if hasattr(row, '_mapping'):
            label = row._mapping['label']
            cnt = row._mapping['cnt']
        else:
            label = row[0]
            cnt = row[1]

        counts_by_label[label] = cnt
        total += cnt

    return total, counts_by_label


def refresh_graph_views(
    engine: Engine,
    concurrent: bool = False,
) -> RefreshResult:
    """
    Refresh graph materialized views.

    Refreshes mv_graph_nodes and mv_graph_links materialized views
    and returns detailed metrics about the operation.

    Args:
        engine: SQLAlchemy database engine
        concurrent: If True, use REFRESH CONCURRENTLY (allows concurrent reads).
                   Requires unique index on the materialized views.

    Returns:
        RefreshResult with operation metrics

    Example:
        >>> from services.graph_refresh import refresh_graph_views
        >>> result = refresh_graph_views(engine, concurrent=True)
        >>> print(f"Nodes: {result.nodes_count}, Links: {result.links_count}")
        >>> print(f"Duration: {result.duration_seconds:.2f}s")
    """
    result = RefreshResult(
        concurrent_refresh=concurrent,
        refreshed_at=datetime.now(timezone.utc),
    )

    start_time = datetime.now(timezone.utc)

    try:
        with engine.begin() as conn:
            # Refresh mv_graph_nodes
            logger.info("Refreshing mv_graph_nodes...")
            try:
                _refresh_materialized_view(conn, "mv_graph_nodes", concurrent)
            except Exception as e:
                result.errors.append(f"mv_graph_nodes refresh failed: {str(e)}")
                logger.error(f"Failed to refresh mv_graph_nodes: {e}")

            # Refresh mv_graph_links
            logger.info("Refreshing mv_graph_links...")
            try:
                _refresh_materialized_view(conn, "mv_graph_links", concurrent)
            except Exception as e:
                result.errors.append(f"mv_graph_links refresh failed: {str(e)}")
                logger.error(f"Failed to refresh mv_graph_links: {e}")

            # Get counts (only if refreshes succeeded)
            if not result.errors:
                try:
                    result.nodes_count, result.nodes_by_type = _get_node_counts(conn)
                except Exception as e:
                    result.errors.append(f"Node count failed: {str(e)}")
                    logger.error(f"Failed to get node counts: {e}")

                try:
                    result.links_count, result.links_by_label = _get_link_counts(conn)
                except Exception as e:
                    result.errors.append(f"Link count failed: {str(e)}")
                    logger.error(f"Failed to get link counts: {e}")

    except Exception as e:
        result.errors.append(f"Database error: {str(e)}")
        logger.error(f"Database error during refresh: {e}")

    end_time = datetime.now(timezone.utc)
    result.duration_seconds = (end_time - start_time).total_seconds()

    if result.success:
        logger.info(
            f"Graph refresh complete: {result.nodes_count} nodes, "
            f"{result.links_count} links in {result.duration_seconds:.2f}s"
        )
    else:
        logger.error(f"Graph refresh failed with {len(result.errors)} errors")

    return result


def main() -> int:
    """
    CLI entrypoint for graph refresh.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Refresh graph materialized views"
    )
    parser.add_argument(
        "--concurrent",
        action="store_true",
        help="Use REFRESH CONCURRENTLY (allows concurrent reads)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not args.database_url:
        logger.error("DATABASE_URL not set. Use --database-url or set environment variable.")
        return 1

    try:
        engine = create_engine(args.database_url)
        result = refresh_graph_views(engine, concurrent=args.concurrent)

        if result.success:
            print(f"Refresh complete!")
            print(f"  Nodes: {result.nodes_count}")
            for node_type, count in result.nodes_by_type.items():
                print(f"    - {node_type}: {count}")
            print(f"  Links: {result.links_count}")
            for label, count in result.links_by_label.items():
                print(f"    - {label}: {count}")
            print(f"  Duration: {result.duration_seconds:.2f}s")
            print(f"  Concurrent: {result.concurrent_refresh}")
            return 0
        else:
            print("Refresh failed with errors:")
            for error in result.errors:
                print(f"  - {error}")
            return 1

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
