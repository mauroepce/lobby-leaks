"""
PostgreSQL database connector with upsert functionality.

This module provides database connectivity using SQLAlchemy 2.x and implements
upsert operations using PostgreSQL's INSERT ... ON CONFLICT syntax.
"""

from typing import Any, Dict, List, Optional, Union
from sqlalchemy import Engine, create_engine, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import Insert
import structlog

logger = structlog.get_logger(__name__)


def get_engine(dsn: str, **kwargs) -> Engine:
    """
    Create and return a SQLAlchemy engine for PostgreSQL.

    Args:
        dsn: PostgreSQL connection string (e.g., "postgresql://user:pass@host:port/db")
        **kwargs: Additional arguments passed to create_engine()

    Returns:
        SQLAlchemy Engine instance

    Example:
        >>> engine = get_engine("postgresql://user:pass@localhost:5432/mydb")
        >>> with engine.connect() as conn:
        ...     result = conn.execute(text("SELECT 1"))
    """
    # Default configuration optimized for PostgreSQL
    default_kwargs = {
        "echo": False,  # Set to True for SQL logging in development
        "pool_pre_ping": True,  # Verify connections before use
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "connect_args": {
            "application_name": "lobbyleaks_service",
        }
    }

    # Merge user kwargs with defaults
    default_kwargs.update(kwargs)

    logger.info("Creating database engine", dsn_host=dsn.split('@')[-1].split('/')[0] if '@' in dsn else 'unknown')

    return create_engine(dsn, **default_kwargs)


def upsert(
    table: Table,
    conflict_keys: Union[str, List[str]],
    payload: Dict[str, Any],
    update_cols: Optional[List[str]] = None,
    do_nothing: bool = False
) -> Insert:
    """
    Create an upsert statement using PostgreSQL's INSERT ... ON CONFLICT syntax.

    This function creates a PostgreSQL-specific upsert operation that will either
    insert a new row or update an existing row based on conflict detection.

    Args:
        table: SQLAlchemy Table object
        conflict_keys: Column name(s) that define the conflict target. Can be:
            - Single column name as string: "id"
            - Multiple columns as list: ["user_id", "date"]
            - Constraint name as string: "users_email_key"
        payload: Dictionary of column names and values to insert/update
        update_cols: List of column names to update on conflict. If None,
                    updates all columns except conflict keys. If empty list,
                    equivalent to setting do_nothing=True.
        do_nothing: If True, performs INSERT ... ON CONFLICT DO NOTHING

    Returns:
        SQLAlchemy Insert statement with ON CONFLICT clause

    Raises:
        ValueError: If conflict_keys is empty or invalid

    Examples:
        Basic upsert by primary key:
        >>> stmt = upsert(
        ...     table=users_table,
        ...     conflict_keys="id",
        ...     payload={"id": 1, "name": "John", "email": "john@example.com"}
        ... )

        Upsert with multiple conflict keys:
        >>> stmt = upsert(
        ...     table=user_stats_table,
        ...     conflict_keys=["user_id", "date"],
        ...     payload={"user_id": 1, "date": "2025-01-01", "views": 10},
        ...     update_cols=["views"]  # Only update views column
        ... )

        Insert or do nothing (ignore conflicts):
        >>> stmt = upsert(
        ...     table=unique_events_table,
        ...     conflict_keys="event_id",
        ...     payload={"event_id": "abc123", "data": "..."},
        ...     do_nothing=True
        ... )

        Using constraint name:
        >>> stmt = upsert(
        ...     table=users_table,
        ...     conflict_keys="users_email_key",  # constraint name
        ...     payload={"email": "user@example.com", "name": "User"}
        ... )

    Notes:
        - conflict_keys can reference either column names or constraint names
        - For column-based conflicts, columns must have a unique index/constraint
        - When using constraint names, reference the actual constraint name in DB
        - If update_cols is None, all payload columns except conflict keys are updated
        - The statement must be executed with engine.execute() or similar
    """
    if not conflict_keys:
        raise ValueError("conflict_keys cannot be empty")

    if not payload:
        raise ValueError("payload cannot be empty")

    # Normalize conflict_keys to list
    if isinstance(conflict_keys, str):
        conflict_keys_list = [conflict_keys]
    else:
        conflict_keys_list = list(conflict_keys)

    # Create insert statement
    stmt = insert(table).values(**payload)

    # Handle DO NOTHING case
    if do_nothing or (update_cols is not None and len(update_cols) == 0):
        logger.debug(
            "Creating upsert with DO NOTHING",
            table=table.name,
            conflict_keys=conflict_keys_list
        )
        return stmt.on_conflict_do_nothing(index_elements=conflict_keys_list)

    # Determine columns to update
    if update_cols is None:
        # Update all columns except conflict keys
        update_cols = [col for col in payload.keys() if col not in conflict_keys_list]

    if not update_cols:
        logger.warning(
            "No columns to update, equivalent to DO NOTHING",
            table=table.name,
            conflict_keys=conflict_keys_list,
            payload_keys=list(payload.keys())
        )
        return stmt.on_conflict_do_nothing(index_elements=conflict_keys_list)

    # Create update dict for ON CONFLICT DO UPDATE
    update_dict = {
        col: stmt.excluded[col] for col in update_cols
    }

    logger.debug(
        "Creating upsert with DO UPDATE",
        table=table.name,
        conflict_keys=conflict_keys_list,
        update_cols=update_cols
    )

    return stmt.on_conflict_do_update(
        index_elements=conflict_keys_list,
        set_=update_dict
    )