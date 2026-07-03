"""structlog configuration with JSON rendering.

All bridge log output flows through structlog; the Datadog agent collects the
JSON lines from container stdout. Log events carry the operation_key and
app_name bound context wherever a CR lifecycle action is involved.
"""

import logging
import sys

import structlog


def configure_logging(log_level: str, service_name: str, env: str) -> None:
    """Configure structlog for JSON output to stdout.

    Args:
        log_level: Standard Python log level name (e.g. "INFO", "DEBUG").
        service_name: Value bound to every event as `service`.
        env: Value bound to every event as `env`.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service=service_name, env=env)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
