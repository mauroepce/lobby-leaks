"""
Tests for PostgreSQL upsert functionality.

These tests verify the database connector's upsert operations using real
PostgreSQL connections and temporary tables for idempotency testing.
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, Mock
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, DateTime, Boolean,
    UniqueConstraint, Index, text, select
)
from sqlalchemy.exc import IntegrityError, ProgrammingError
from datetime import datetime

from services._template.db.connector import get_engine, upsert


# Mark all tests in this module as database tests
pytestmark = pytest.mark.db


class TestGetEngine:
    """Test database engine creation."""

    def test_get_engine_with_valid_dsn(self):
        """Test engine creation with valid DSN."""
        dsn = "postgresql+psycopg://user:pass@localhost:5432/testdb"
        engine = get_engine(dsn)

        assert engine is not None
        assert "postgresql" in str(engine.url)

    def test_get_engine_with_kwargs(self):
        """Test engine creation with additional kwargs."""
        dsn = "postgresql+psycopg://user:pass@localhost:5432/testdb"
        engine = get_engine(dsn, echo=True, pool_size=10)

        assert engine.echo is True

    @patch('services._template.db.connector.create_engine')
    def test_get_engine_calls_create_engine_with_defaults(self, mock_create_engine):
        """Test that get_engine calls create_engine with proper defaults."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        dsn = "postgresql+psycopg://user:pass@localhost:5432/testdb"
        result = get_engine(dsn)

        mock_create_engine.assert_called_once()
        args, kwargs = mock_create_engine.call_args
        assert args[0] == dsn
        assert kwargs['pool_pre_ping'] is True
        assert kwargs['pool_recycle'] == 3600
        assert 'application_name' in kwargs['connect_args']
        assert result == mock_engine


class TestUpsertStatementGeneration:
    """Test upsert statement generation without database connection."""

    def setUp(self):
        """Set up test fixtures."""
        self.metadata = MetaData()

        # Users table with single primary key
        self.users_table = Table(
            'users', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(100), nullable=False),
            Column('email', String(255), nullable=False),
            Column('is_active', Boolean, default=True),
            UniqueConstraint('email', name='users_email_key')
        )

        # User stats table with composite primary key
        self.user_stats_table = Table(
            'user_stats', self.metadata,
            Column('user_id', Integer, nullable=False),
            Column('date', String(10), nullable=False),  # YYYY-MM-DD
            Column('views', Integer, default=0),
            Column('clicks', Integer, default=0),
            Column('created_at', DateTime, default=datetime.utcnow),
            UniqueConstraint('user_id', 'date', name='user_stats_unique')
        )

    def test_upsert_basic_single_key(self):
        """Test basic upsert with single conflict key."""
        self.setUp()

        payload = {"id": 1, "name": "John", "email": "john@example.com"}
        stmt = upsert(
            table=self.users_table,
            conflict_keys="id",
            payload=payload
        )

        # Verify it's an insert statement with on_conflict
        assert hasattr(stmt, 'on_conflict_do_update')
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()

        assert "insert into users" in sql
        assert "on conflict" in sql
        assert "do update" in sql

    def test_upsert_multiple_conflict_keys(self):
        """Test upsert with multiple conflict keys."""
        self.setUp()

        payload = {"user_id": 1, "date": "2025-01-01", "views": 10, "clicks": 2}
        stmt = upsert(
            table=self.user_stats_table,
            conflict_keys=["user_id", "date"],
            payload=payload
        )

        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()

        assert "insert into user_stats" in sql
        assert "on conflict" in sql
        assert "user_id" in sql
        assert "date" in sql

    def test_upsert_with_specific_update_cols(self):
        """Test upsert with specific columns to update."""
        self.setUp()

        payload = {"user_id": 1, "date": "2025-01-01", "views": 10, "clicks": 2}
        stmt = upsert(
            table=self.user_stats_table,
            conflict_keys=["user_id", "date"],
            payload=payload,
            update_cols=["views"]  # Only update views
        )

        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()

        assert "views = excluded.views" in sql
        assert "clicks = excluded.clicks" not in sql

    def test_upsert_do_nothing_explicit(self):
        """Test upsert with explicit do_nothing=True."""
        self.setUp()

        payload = {"id": 1, "name": "John", "email": "john@example.com"}
        stmt = upsert(
            table=self.users_table,
            conflict_keys="id",
            payload=payload,
            do_nothing=True
        )

        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()

        assert "on conflict" in sql
        assert "do nothing" in sql
        assert "do update" not in sql

    def test_upsert_do_nothing_empty_update_cols(self):
        """Test upsert with empty update_cols list (equivalent to do_nothing)."""
        self.setUp()

        payload = {"id": 1, "name": "John", "email": "john@example.com"}
        stmt = upsert(
            table=self.users_table,
            conflict_keys="id",
            payload=payload,
            update_cols=[]  # Empty list = do nothing
        )

        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()

        assert "do nothing" in sql

    def test_upsert_constraint_name(self):
        """Test upsert using constraint name instead of column names."""
        self.setUp()

        payload = {"email": "user@example.com", "name": "User", "is_active": True}
        stmt = upsert(
            table=self.users_table,
            conflict_keys="users_email_key",  # constraint name
            payload=payload
        )

        # Should generate valid statement
        assert hasattr(stmt, 'on_conflict_do_update')

    def test_upsert_error_empty_conflict_keys(self):
        """Test upsert raises error with empty conflict keys."""
        self.setUp()

        payload = {"id": 1, "name": "John"}

        with pytest.raises(ValueError, match="conflict_keys cannot be empty"):
            upsert(
                table=self.users_table,
                conflict_keys=[],
                payload=payload
            )

    def test_upsert_error_empty_payload(self):
        """Test upsert raises error with empty payload."""
        self.setUp()

        with pytest.raises(ValueError, match="payload cannot be empty"):
            upsert(
                table=self.users_table,
                conflict_keys="id",
                payload={}
            )


@pytest.mark.integration
class TestUpsertDatabaseIntegration:
    """Integration tests for upsert with real database operations."""

    @pytest.fixture
    def engine(self):
        """Provide database engine for testing."""
        # Use environment variable or default test database
        import os
        dsn = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://lobbyleaks:l0bby@localhost:5432/lobbyleaks")
        return get_engine(dsn)

    @pytest.fixture
    def test_tables(self, engine):
        """Create temporary test tables."""
        metadata = MetaData()

        # Simple users table
        users_table = Table(
            'test_users', metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(100), nullable=False),
            Column('email', String(255), nullable=False),
            Column('is_active', Boolean, default=True),
            UniqueConstraint('email', name='test_users_email_key')
        )

        # Stats table with composite key
        stats_table = Table(
            'test_user_stats', metadata,
            Column('user_id', Integer, nullable=False),
            Column('date', String(10), nullable=False),
            Column('views', Integer, default=0),
            Column('clicks', Integer, default=0),
            UniqueConstraint('user_id', 'date', name='test_stats_unique')
        )

        # Create tables
        metadata.create_all(bind=engine)

        yield {'users': users_table, 'stats': stats_table}

        # Cleanup
        metadata.drop_all(bind=engine)

    def test_upsert_insert_new_record(self, engine, test_tables):
        """Test upsert creates new record when no conflict."""
        users_table = test_tables['users']

        payload = {"id": 1, "name": "John Doe", "email": "john@example.com", "is_active": True}
        stmt = upsert(
            table=users_table,
            conflict_keys="id",
            payload=payload
        )

        with engine.connect() as conn:
            # Execute upsert
            result = conn.execute(stmt)
            conn.commit()

            # Verify record was inserted
            select_stmt = select(users_table).where(users_table.c.id == 1)
            row = conn.execute(select_stmt).fetchone()

            assert row is not None
            assert row.name == "John Doe"
            assert row.email == "john@example.com"
            assert row.is_active is True

    def test_upsert_update_existing_record(self, engine, test_tables):
        """Test upsert updates existing record on conflict."""
        users_table = test_tables['users']

        # First insert
        payload1 = {"id": 1, "name": "John Doe", "email": "john@example.com", "is_active": True}
        stmt1 = upsert(table=users_table, conflict_keys="id", payload=payload1)

        # Second insert with same ID but different data
        payload2 = {"id": 1, "name": "John Smith", "email": "johnsmith@example.com", "is_active": False}
        stmt2 = upsert(table=users_table, conflict_keys="id", payload=payload2)

        with engine.connect() as conn:
            # Execute first upsert
            conn.execute(stmt1)
            conn.commit()

            # Execute second upsert (should update)
            conn.execute(stmt2)
            conn.commit()

            # Verify record was updated
            select_stmt = select(users_table).where(users_table.c.id == 1)
            row = conn.execute(select_stmt).fetchone()

            assert row is not None
            assert row.name == "John Smith"  # Updated
            assert row.email == "johnsmith@example.com"  # Updated
            assert row.is_active is False  # Updated

    def test_upsert_partial_update(self, engine, test_tables):
        """Test upsert with partial column updates."""
        users_table = test_tables['users']

        # First insert
        payload1 = {"id": 1, "name": "John Doe", "email": "john@example.com", "is_active": True}
        stmt1 = upsert(table=users_table, conflict_keys="id", payload=payload1)

        # Second insert updating only name
        payload2 = {"id": 1, "name": "John Smith", "email": "new@example.com", "is_active": False}
        stmt2 = upsert(
            table=users_table,
            conflict_keys="id",
            payload=payload2,
            update_cols=["name"]  # Only update name
        )

        with engine.connect() as conn:
            # Execute first upsert
            conn.execute(stmt1)
            conn.commit()

            # Execute second upsert (should only update name)
            conn.execute(stmt2)
            conn.commit()

            # Verify only name was updated
            select_stmt = select(users_table).where(users_table.c.id == 1)
            row = conn.execute(select_stmt).fetchone()

            assert row is not None
            assert row.name == "John Smith"  # Updated
            assert row.email == "john@example.com"  # NOT updated
            assert row.is_active is True  # NOT updated

    def test_upsert_do_nothing_conflict(self, engine, test_tables):
        """Test upsert with do_nothing ignores conflicts."""
        users_table = test_tables['users']

        # First insert
        payload1 = {"id": 1, "name": "John Doe", "email": "john@example.com", "is_active": True}
        stmt1 = upsert(table=users_table, conflict_keys="id", payload=payload1)

        # Second insert with do_nothing
        payload2 = {"id": 1, "name": "John Smith", "email": "johnsmith@example.com", "is_active": False}
        stmt2 = upsert(
            table=users_table,
            conflict_keys="id",
            payload=payload2,
            do_nothing=True
        )

        with engine.connect() as conn:
            # Execute first upsert
            conn.execute(stmt1)
            conn.commit()

            # Execute second upsert (should do nothing)
            conn.execute(stmt2)
            conn.commit()

            # Verify original record unchanged
            select_stmt = select(users_table).where(users_table.c.id == 1)
            row = conn.execute(select_stmt).fetchone()

            assert row is not None
            assert row.name == "John Doe"  # Unchanged
            assert row.email == "john@example.com"  # Unchanged
            assert row.is_active is True  # Unchanged

    def test_upsert_composite_key(self, engine, test_tables):
        """Test upsert with composite conflict keys."""
        stats_table = test_tables['stats']

        # First insert
        payload1 = {"user_id": 1, "date": "2025-01-01", "views": 10, "clicks": 2}
        stmt1 = upsert(
            table=stats_table,
            conflict_keys=["user_id", "date"],
            payload=payload1
        )

        # Second insert with same composite key
        payload2 = {"user_id": 1, "date": "2025-01-01", "views": 20, "clicks": 5}
        stmt2 = upsert(
            table=stats_table,
            conflict_keys=["user_id", "date"],
            payload=payload2
        )

        with engine.connect() as conn:
            # Execute first upsert
            conn.execute(stmt1)
            conn.commit()

            # Execute second upsert (should update)
            conn.execute(stmt2)
            conn.commit()

            # Verify record was updated
            select_stmt = select(stats_table).where(
                (stats_table.c.user_id == 1) & (stats_table.c.date == "2025-01-01")
            )
            row = conn.execute(select_stmt).fetchone()

            assert row is not None
            assert row.views == 20  # Updated
            assert row.clicks == 5  # Updated

    def test_upsert_idempotency(self, engine, test_tables):
        """Test that repeated upserts are idempotent."""
        users_table = test_tables['users']

        payload = {"id": 1, "name": "John Doe", "email": "john@example.com", "is_active": True}
        stmt = upsert(table=users_table, conflict_keys="id", payload=payload)

        with engine.connect() as conn:
            # Execute same upsert multiple times
            for _ in range(3):
                conn.execute(stmt)
                conn.commit()

            # Verify only one record exists
            count_stmt = select(users_table).where(users_table.c.id == 1)
            rows = conn.execute(count_stmt).fetchall()

            assert len(rows) == 1
            assert rows[0].name == "John Doe"

    def test_upsert_invalid_conflict_key_error(self, engine, test_tables):
        """Test upsert with invalid conflict key raises appropriate error."""
        users_table = test_tables['users']

        payload = {"id": 1, "name": "John Doe", "email": "john@example.com"}
        stmt = upsert(
            table=users_table,
            conflict_keys="nonexistent_column",  # Invalid column
            payload=payload
        )

        with engine.connect() as conn:
            # Should raise error when executed
            with pytest.raises((IntegrityError, ProgrammingError)):
                conn.execute(stmt)
                conn.commit()