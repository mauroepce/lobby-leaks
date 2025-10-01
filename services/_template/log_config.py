"""
Structured logging configuration using structlog.

Provides JSON logging with ISO timestamps and stdlib compatibility.
All log messages are structured and include contextual information.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.typing import FilteringBoundLogger

# Import settings with lazy loading to avoid circular imports
def _get_settings():
    """Lazy load settings to avoid circular imports."""
    try:
        from .settings import settings
        return settings()
    except ImportError:
        # Fallback for tests
        class MockSettings:
            log_level = "INFO"
            log_format = "json"
            service_name = "test-service"
            environment = "test"
        return MockSettings()


def configure_logging(log_level: str = None, log_format: str = None) -> None:
    """
    Configure structlog with JSON output and stdlib compatibility.

    Args:
        log_level: Override log level from settings
        log_format: Override log format from settings
    """
    config = _get_settings()
    level = log_level or config.log_level
    format_type = log_format or config.log_format

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level),
    )

    # Common processors for all log entries
    processors = [
        # Add service name and environment to all logs
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,

        # Add service metadata
        lambda _, __, event_dict: {
            **event_dict,
            "service": config.service_name,
            "environment": config.environment,
        },
    ]

    # Choose renderer based on format
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development-friendly format
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Ensure stdlib loggers also use structlog
    structlog.stdlib.recreate_defaults(log_level=level)


def get_logger(name: str = None) -> FilteringBoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (defaults to caller's module)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> Dict[str, Any]:
    """
    Create a context dictionary for logging.

    Args:
        **kwargs: Key-value pairs to include in log context

    Returns:
        Context dictionary suitable for structlog.bind()
    """
    return kwargs


class StructlogMiddleware:
    """
    Middleware to add request context to all log messages.

    Example usage with FastAPI:
        app.add_middleware(StructlogMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request information
        request_id = scope.get("headers", {}).get("x-request-id", "unknown")
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        # Bind context for this request
        with structlog.contextvars.bound_contextvars(
            request_id=request_id,
            method=method,
            path=path,
        ):
            await self.app(scope, receive, send)


# Convenience functions for common logging patterns
def log_api_call(
    logger: FilteringBoundLogger,
    method: str,
    url: str,
    status_code: int = None,
    duration_ms: float = None,
    **extra_context
) -> None:
    """
    Log an API call with structured information.

    Args:
        logger: Logger instance
        method: HTTP method
        url: Request URL
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **extra_context: Additional context to include
    """
    context = {
        "method": method,
        "url": url,
        **extra_context
    }

    if status_code is not None:
        context["status_code"] = status_code

    if duration_ms is not None:
        context["duration_ms"] = round(duration_ms, 2)

    # Choose log level based on status code
    if status_code and status_code >= 500:
        logger.error("API call failed", **context)
    elif status_code and status_code >= 400:
        logger.warning("API call client error", **context)
    else:
        logger.info("API call completed", **context)


def log_database_operation(
    logger: FilteringBoundLogger,
    operation: str,
    table: str = None,
    duration_ms: float = None,
    rows_affected: int = None,
    **extra_context
) -> None:
    """
    Log a database operation with structured information.

    Args:
        logger: Logger instance
        operation: Database operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration_ms: Operation duration in milliseconds
        rows_affected: Number of rows affected
        **extra_context: Additional context to include
    """
    context = {
        "operation": operation.upper(),
        **extra_context
    }

    if table:
        context["table"] = table

    if duration_ms is not None:
        context["duration_ms"] = round(duration_ms, 2)

    if rows_affected is not None:
        context["rows_affected"] = rows_affected

    logger.info("Database operation completed", **context)


def log_processing_batch(
    logger: FilteringBoundLogger,
    batch_id: str,
    items_processed: int,
    items_failed: int = 0,
    duration_ms: float = None,
    **extra_context
) -> None:
    """
    Log batch processing results.

    Args:
        logger: Logger instance
        batch_id: Unique batch identifier
        items_processed: Number of items successfully processed
        items_failed: Number of items that failed processing
        duration_ms: Processing duration in milliseconds
        **extra_context: Additional context to include
    """
    context = {
        "batch_id": batch_id,
        "items_processed": items_processed,
        "items_failed": items_failed,
        "success_rate": round(items_processed / (items_processed + items_failed) * 100, 2) if (items_processed + items_failed) > 0 else 0,
        **extra_context
    }

    if duration_ms is not None:
        context["duration_ms"] = round(duration_ms, 2)

    if items_failed > 0:
        logger.warning("Batch processing completed with failures", **context)
    else:
        logger.info("Batch processing completed successfully", **context)


# Initialize logging when module is imported (except during testing)
def _initialize_logging():
    """Initialize logging configuration on module import."""
    try:
        # Skip initialization during pytest
        if "pytest" not in sys.modules:
            configure_logging()
    except Exception as e:
        # Fallback to basic logging if configuration fails
        logging.basicConfig(level=logging.INFO)
        if logging.getLogger:  # Check if logging is fully initialized
            logging.getLogger(__name__).error(
                "Failed to configure structured logging: %s", e
            )


# Auto-initialize when module is imported
_initialize_logging()