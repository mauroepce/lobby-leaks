"""
Configuration settings for Lobby Collector service.

Loads configuration from environment variables with validation.
"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LobbyCollectorSettings(BaseSettings):
    """
    Configuration for the Lobby Collector service.

    All settings can be configured via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # API Configuration
    lobby_api_base_url: str = Field(
        default="https://api.leylobby.gob.cl/v1",
        description="Base URL for Ley de Lobby API"
    )

    lobby_api_key: str = Field(
        description="API key for authentication with Ley de Lobby API"
    )

    # Pagination Configuration
    page_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Number of records per page (1-1000)"
    )

    # Temporal Window Configuration
    default_since_days: int = Field(
        default=7,
        ge=1,
        description="Default number of days to look back if --since not specified"
    )

    # HTTP Client Configuration
    api_timeout: float = Field(
        default=30.0,
        gt=0,
        description="Request timeout in seconds"
    )

    api_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retry attempts for failed requests"
    )

    # Rate Limiting
    rate_limit_delay: float = Field(
        default=0.5,
        ge=0,
        description="Delay between requests in seconds (rate limiting)"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )

    service_name: str = Field(
        default="lobby-collector",
        description="Service name for logging and monitoring"
    )


@lru_cache()
def get_settings() -> LobbyCollectorSettings:
    """
    Get cached settings instance.

    Returns:
        Singleton instance of settings
    """
    return LobbyCollectorSettings()


# Convenience alias
settings = get_settings
