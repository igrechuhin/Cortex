"""
Logging configuration for Cortex.

This module provides centralized logging configuration for the entire
Cortex server. It ensures consistent log formatting and output
across all modules.

While this module exposes a global logger instance for convenience, this is
an acceptable exception to the no-global-state rule as:
1. Python's logging module is designed around global loggers
2. Loggers are stateless - they only route messages
3. The logging configuration is immutable after setup

For dependency injection contexts, use setup_logging() to get a logger instance.
"""

import logging
import os
import sys


class _CortexFormatter(logging.Formatter):
    """Formatter that emits: [level] name  - message (no timestamp; client adds one for stderr)."""

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname.lower()
        return f"[{level}] {record.name}  - {record.getMessage()}"


def setup_logging(level: str | None = None) -> logging.Logger:
    """
    Configure logging for Cortex.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If not provided, uses CORTEX_LOG_LEVEL env var or defaults to INFO.

    Returns:
        Configured logger instance for cortex.

    Example:
        >>> logger = setup_logging("DEBUG")
        >>> logger.info("Server started")
    """
    if level is None:
        level = os.getenv("CORTEX_LOG_LEVEL", "INFO")

    logger = logging.getLogger("cortex")
    logger.setLevel(getattr(logging, level.upper()))
    # Prevent propagation to the root logger.
    #
    # The root logger may be configured by third-party libraries (e.g. RichHandler)
    # that write to stdout. Stdout is reserved for the MCP protocol, so any extra
    # output can break the connection and cause Cursor to mark the MCP server as
    # errored (tool descriptors disappear, "tool not found", etc.).
    logger.propagate = False

    # Avoid adding multiple handlers if already configured
    if logger.handlers:
        return logger

    # Send logs to stderr (stdout is reserved for MCP protocol)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_CortexFormatter())
    logger.addHandler(handler)

    # Ensure root has our formatter so loggers that propagate to root use it.
    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(logging.INFO)
        root_handler = logging.StreamHandler(sys.stderr)
        root_handler.setFormatter(_CortexFormatter())
        root.addHandler(root_handler)

    return logger


def apply_cortex_format_to_third_party_loggers() -> None:
    """Make MCP and other third-party loggers use our compact format.

    Call after the MCP package is imported so their loggers exist. Clears
    their handlers and enables propagation to root so messages are formatted
    by the root handler (same style as cortex logs).
    """
    for name in ("mcp", "mcp.server"):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True


# Global logger instance (acceptable exception - Python logging convention)
# For dependency injection, call setup_logging() instead
logger = setup_logging()
