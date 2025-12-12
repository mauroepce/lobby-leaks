"""
Configuration settings for InfoLobby Sync service.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InfoLobbySyncSettings(BaseSettings):
    """Configuration for InfoLobby Sync service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # SPARQL Endpoint Configuration
    infolobby_sparql_endpoint: str = Field(
        default="http://datos.infolobby.cl/sparql",
        description="InfoLobby SPARQL endpoint URL"
    )

    infolobby_default_graph: str = Field(
        default="http://datos.infolobby.cl/infolobby",
        description="Default graph URI for SPARQL queries"
    )

    # Feature Flags
    enable_infolobby_sync: bool = Field(
        default=True,
        description="Enable InfoLobby sync (false = disabled mode)"
    )

    # Query Configuration
    sparql_timeout: int = Field(
        default=120,
        ge=10,
        le=600,
        description="SPARQL query timeout in seconds"
    )

    sparql_batch_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Number of records per SPARQL query"
    )

    # HTTP Client Configuration
    http_timeout: float = Field(
        default=60.0,
        gt=0,
        description="HTTP request timeout in seconds"
    )

    http_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retry attempts"
    )

    # Data Storage
    data_dir: str = Field(
        default="data/info_lobby",
        description="Directory for storing downloaded data and checksums"
    )

    # Database Configuration
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection string"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )

    service_name: str = Field(
        default="info-lobby-sync",
        description="Service name for logging"
    )


@lru_cache()
def get_settings() -> InfoLobbySyncSettings:
    """Get cached settings instance."""
    return InfoLobbySyncSettings()


settings = get_settings
