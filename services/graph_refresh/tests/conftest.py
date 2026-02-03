"""
Pytest fixtures for graph_refresh tests.

Integration tests require DATABASE_URL environment variable.
Tests are skipped if DATABASE_URL is not set.
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_database_url() -> str | None:
    """Get database URL from environment."""
    return os.environ.get("DATABASE_URL")


def requires_database():
    """Decorator to skip tests if DATABASE_URL is not set."""
    db_url = get_database_url()
    return pytest.mark.skipif(
        db_url is None,
        reason="requires PostgreSQL integration DB (set DATABASE_URL)"
    )


@pytest.fixture(scope="module")
def database_url() -> str:
    """
    Get database URL, skip if not set.

    This fixture ensures integration tests only run when
    a real PostgreSQL database is available.
    """
    url = get_database_url()
    if not url:
        pytest.skip("requires PostgreSQL integration DB (set DATABASE_URL)")
    return url


@pytest.fixture(scope="module")
def engine(database_url: str) -> Engine:
    """Create SQLAlchemy engine for integration tests."""
    return create_engine(database_url)
