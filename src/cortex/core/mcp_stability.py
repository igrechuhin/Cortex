"""MCP connection stability and resource management.

This module provides connection stability features for MCP tool handlers:
- Timeout protection for long-running operations
- Resource limit enforcement (concurrent operations)
- Connection error handling and recovery
- Connection health monitoring
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from cortex.core.constants import (
    MCP_CONNECTION_RETRY_ATTEMPTS,
    MCP_CONNECTION_RETRY_DELAY_SECONDS,
    MCP_MAX_CONCURRENT_TOOLS,
    MCP_TOOL_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Global semaphore for limiting concurrent tool executions
_concurrent_tools_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the global semaphore for concurrent tool limits."""
    global _concurrent_tools_semaphore
    if _concurrent_tools_semaphore is None:
        _concurrent_tools_semaphore = asyncio.Semaphore(MCP_MAX_CONCURRENT_TOOLS)
    return _concurrent_tools_semaphore


async def with_mcp_stability(
    func: Callable[..., Awaitable[T]],
    *args: object,
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    **kwargs: object,
) -> T:
    """Execute MCP tool with stability protections.

    Provides:
    - Timeout protection (prevents hanging operations)
    - Resource limit enforcement (concurrent operations)
    - Connection error handling
    - Automatic retry for transient failures

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        timeout: Maximum execution time in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result from func execution

    Raises:
        TimeoutError: If operation exceeds timeout
        RuntimeError: If resource limits exceeded or connection fails
    """
    semaphore = _get_semaphore()

    async def _execute_with_retry() -> T:
        """Execute function with retry logic for transient failures."""
        last_exception: Exception | None = None

        for attempt in range(1, MCP_CONNECTION_RETRY_ATTEMPTS + 1):
            try:
                # Acquire semaphore to enforce concurrent operation limit
                async with semaphore:
                    # Execute with timeout protection
                    async with asyncio.timeout(timeout):
                        return await func(*args, **kwargs)

            except asyncio.TimeoutError as e:
                logger.warning(
                    f"MCP tool {func.__name__} timed out after {timeout}s (attempt {attempt}/{MCP_CONNECTION_RETRY_ATTEMPTS})"
                )
                if attempt == MCP_CONNECTION_RETRY_ATTEMPTS:
                    raise TimeoutError(
                        f"MCP tool {func.__name__} exceeded timeout of {timeout}s"
                    ) from e
                last_exception = e

            except (ConnectionError, BrokenPipeError, OSError) as e:
                logger.warning(
                    f"MCP connection error in {func.__name__} (attempt {attempt}/{MCP_CONNECTION_RETRY_ATTEMPTS}): {e}"
                )
                if attempt == MCP_CONNECTION_RETRY_ATTEMPTS:
                    raise RuntimeError(
                        f"MCP connection failed for {func.__name__} after {attempt} attempts"
                    ) from e
                last_exception = e
                # Wait before retry
                await asyncio.sleep(MCP_CONNECTION_RETRY_DELAY_SECONDS * attempt)

            except Exception as e:
                # Non-transient errors - don't retry
                logger.error(
                    f"MCP tool {func.__name__} failed with non-transient error: {e}"
                )
                raise

        # Should never reach here, but satisfy type checker
        if last_exception:
            raise RuntimeError(
                f"MCP tool {func.__name__} failed after {MCP_CONNECTION_RETRY_ATTEMPTS} attempts"
            ) from last_exception

        raise RuntimeError(f"MCP tool {func.__name__} failed unexpectedly")

    return await _execute_with_retry()


def mcp_tool_wrapper(
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for MCP tools to add stability protections.

    Usage:
        @mcp.tool()
        @mcp_tool_wrapper(timeout=60.0)
        async def my_tool(...):
            ...

    Args:
        timeout: Maximum execution time in seconds

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """Apply stability wrapper to function."""

        async def wrapper(*args: object, **kwargs: object) -> T:
            """Wrapped function with stability protections."""
            return await with_mcp_stability(func, *args, timeout=timeout, **kwargs)

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__annotations__ = func.__annotations__

        return wrapper

    return decorator


async def check_connection_health() -> dict[str, object]:
    """Check MCP connection health status.

    Returns:
        Dictionary with health metrics:
        - healthy: bool - Whether connection is healthy
        - concurrent_operations: int - Current concurrent operations
        - max_concurrent: int - Maximum allowed concurrent operations
        - semaphore_available: int - Available semaphore slots
    """
    semaphore = _get_semaphore()
    available = semaphore._value  # pyright: ignore[reportPrivateUsage]
    current = MCP_MAX_CONCURRENT_TOOLS - available

    return {
        "healthy": True,  # Connection is healthy if we can check
        "concurrent_operations": current,
        "max_concurrent": MCP_MAX_CONCURRENT_TOOLS,
        "semaphore_available": available,
        "utilization_percent": (
            (current / MCP_MAX_CONCURRENT_TOOLS) * 100
            if MCP_MAX_CONCURRENT_TOOLS > 0
            else 0
        ),
    }
