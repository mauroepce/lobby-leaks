"""
Configuration management using Pydantic Settings.

Loads configuration from environment variables and .env files
with validation and type conversion.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.

    Settings are loaded in this order of precedence:
    1. Environment variables
    2. .env file in current directory
    3. Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # API Configuration
    api_key: str = Field(
        description="API key for external service authentication"
    )

    api_base_url: str = Field(
        default="https://api.example.com",
        description="Base URL for the external API"
    )

    api_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="API request timeout in seconds"
    )

    api_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts for failed requests"
    )

    # Database Configuration
    db_dsn: Optional[str] = Field(
        default=None,
        description="Database connection string (PostgreSQL DSN)"
    )

    db_pool_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Database connection pool size"
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    log_format: str = Field(
        default="json",
        description="Log output format (json, text)"
    )

    # Service-specific Configuration
    service_name: str = Field(
        default="lobbyleaks-service",
        description="Service name for logging and monitoring"
    )

    environment: str = Field(
        default="development",
        description="Environment name (development, staging, production)"
    )

    # Rate Limiting
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Maximum requests per minute"
    )

    rate_limit_window: int = Field(
        default=60,
        ge=1,
        description="Rate limit window in seconds"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is one of the standard levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v):
        """Validate log format is supported."""
        valid_formats = {"json", "text"}
        if v.lower() not in valid_formats:
            raise ValueError(f"log_format must be one of: {', '.join(valid_formats)}")
        return v.lower()

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment name."""
        valid_envs = {"development", "staging", "production"}
        if v.lower() not in valid_envs:
            raise ValueError(f"environment must be one of: {', '.join(valid_envs)}")
        return v.lower()

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v):
        """Validate API key is not empty."""
        if not v or not v.strip():
            raise ValueError("api_key cannot be empty")
        return v.strip()

    @field_validator("db_dsn")
    @classmethod
    def validate_db_dsn(cls, v):
        """Validate database DSN format if provided."""
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        # Basic validation for PostgreSQL DSN
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("db_dsn must be a valid PostgreSQL connection string")

        return v

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def get_api_headers(self) -> dict:
        """Get standard API headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": f"{self.service_name}/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }



@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses LRU cache to avoid re-reading configuration files
    on every function call. Cache size is 1 to ensure
    settings are loaded only once per process.

    Returns:
        Settings instance with loaded configuration
    """
    return Settings()


# Convenience function to get settings
def settings() -> Settings:
    """Get application settings."""
    return get_settings()