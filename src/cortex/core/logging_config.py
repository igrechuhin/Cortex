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

    # Avoid adding multiple handlers if already configured
    if logger.handlers:
        return logger

    # Send logs to stderr (stdout is reserved for MCP protocol)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)

    return logger


# Global logger instance (acceptable exception - Python logging convention)
# For dependency injection, call setup_logging() instead
logger = setup_logging()
