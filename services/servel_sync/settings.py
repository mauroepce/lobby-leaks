"""
Configuration settings for SERVEL Sync service.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServelSyncSettings(BaseSettings):
    """Configuration for SERVEL Sync service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Feature Flags
    enable_servel_sync: bool = Field(
        default=True,
        description="Enable SERVEL sync (false = disabled mode)"
    )

    # HTTP Client Configuration (for remote URL fetching)
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
        default="data/servel",
        description="Directory for storing downloaded data and reports"
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
        default="servel-sync",
        description="Service name for logging"
    )


@lru_cache()
def get_settings() -> ServelSyncSettings:
    """Get cached settings instance."""
    return ServelSyncSettings()


settings = get_settings
