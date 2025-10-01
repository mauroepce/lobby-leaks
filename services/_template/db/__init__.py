"""
Database connectivity module for LobbyLeaks services.

This module provides PostgreSQL database connectivity with upsert capabilities
using SQLAlchemy 2.x and psycopg3.
"""

from .connector import get_engine, upsert

__all__ = ["get_engine", "upsert"]