"""Connection health monitoring for pre-commit test execution.

Extracted from pre_commit_tools to keep it under 400 lines.
"""

import logging

from cortex.core.mcp_stability import check_connection_health
from cortex.core.models import ConnectionHealth

logger = logging.getLogger(__name__)


async def log_connection_health_before_tests() -> ConnectionHealth | None:
    """Log connection health before test execution (Step 12.7 monitoring)."""
    try:
        health = await check_connection_health()
        logger.info(
            "execute_pre_commit_checks: connection health before tests: %s",
            health.model_dump(),
        )
        return health
    except Exception as e:
        logger.warning(
            "execute_pre_commit_checks: failed to check connection health before tests: %s",
            e,
        )
        return None


async def log_connection_health_after_tests(
    health_before: ConnectionHealth | None,
) -> None:
    """Log connection health after successful test execution (Step 12.7 monitoring)."""
    try:
        health_after = await check_connection_health()
        logger.info(
            "execute_pre_commit_checks: connection health after tests: %s (health_before=%s)",
            health_after.model_dump(),
            health_before.model_dump() if health_before else None,
        )
    except Exception as e:
        logger.warning(
            "execute_pre_commit_checks: failed to check connection health after tests: %s",
            e,
        )


def log_test_execution_error(
    error: Exception, health_before: ConnectionHealth | None
) -> None:
    """Log test execution error with connection health context."""
    logger.error(
        "execute_pre_commit_checks: test execution failed: %s (health_before=%s)",
        error,
        health_before,
    )
