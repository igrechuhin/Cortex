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

import anyio

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


async def _handle_timeout_error(
    func_name: str, timeout: float, attempt: int, e: asyncio.TimeoutError
) -> tuple[TimeoutError | None, Exception | None]:
    """Handle timeout error during retry.

    Args:
        func_name: Name of the function that timed out
        timeout: Timeout value in seconds
        attempt: Current attempt number
        e: The timeout exception

    Returns:
        Tuple of (error to raise if final attempt, exception to store)
    """
    logger.warning(
        f"MCP tool {func_name} timed out after {timeout}s (attempt {attempt}/{MCP_CONNECTION_RETRY_ATTEMPTS})"
    )
    if attempt == MCP_CONNECTION_RETRY_ATTEMPTS:
        error = TimeoutError(f"MCP tool {func_name} exceeded timeout of {timeout}s")
        error.__cause__ = e
        return error, None
    return None, e


async def _handle_connection_error(
    func_name: str, attempt: int, e: Exception
) -> tuple[RuntimeError | None, Exception | None]:
    """Handle connection error during retry.

    Args:
        func_name: Name of the function that failed
        attempt: Current attempt number
        e: The connection exception

    Returns:
        Tuple of (error to raise if final attempt, exception to store)
    """
    logger.warning(
        f"MCP connection error in {func_name} (attempt {attempt}/{MCP_CONNECTION_RETRY_ATTEMPTS}): {e}"
    )
    if attempt == MCP_CONNECTION_RETRY_ATTEMPTS:
        error = RuntimeError(
            f"MCP connection failed for {func_name} after {attempt} attempts"
        )
        error.__cause__ = e
        return error, None
    await asyncio.sleep(MCP_CONNECTION_RETRY_DELAY_SECONDS * attempt)
    return None, e


async def _execute_single_attempt(
    func: Callable[..., Awaitable[T]],
    semaphore: asyncio.Semaphore,
    timeout: float,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> T:
    """Execute function once with timeout and resource limits."""
    async with semaphore:
        async with asyncio.timeout(timeout):
            return await func(*args, **kwargs)


def _is_connection_error(e: Exception) -> bool:
    """Check if exception is connection-related.

    Args:
        e: Exception to check

    Returns:
        True if exception is connection-related
    """
    connection_error_types = (
        ConnectionError,
        BrokenPipeError,
        OSError,
        RuntimeError,  # FastMCP may raise RuntimeError for connection issues
        anyio.BrokenResourceError,  # anyio resource errors (e.g., stdio closed)
    )

    if isinstance(e, connection_error_types):
        return True

    error_message = str(e).lower()
    connection_keywords = [
        "connection",
        "broken pipe",
        "connection reset",
        "tool not found",
        "resource",
        "stdio",
    ]

    return any(keyword in error_message for keyword in connection_keywords)


async def _handle_retry_exception(
    func_name: str,
    timeout: float,
    attempt: int,
    e: Exception,
    last_exception: Exception | None,
) -> tuple[bool, Exception | None]:
    """Handle exception during retry attempt.

    Returns:
        Tuple of (should_raise, new_last_exception)
    """
    if isinstance(e, asyncio.TimeoutError):
        error, stored_exception = await _handle_timeout_error(
            func_name, timeout, attempt, e
        )
        if error:
            raise error
        return False, stored_exception

    if _is_connection_error(e):
        error, stored_exception = await _handle_connection_error(func_name, attempt, e)
        if error:
            raise error
        return False, stored_exception

    logger.error(f"MCP tool {func_name} failed: {e}")
    raise


async def _execute_with_retry(
    func: Callable[..., Awaitable[T]],
    semaphore: asyncio.Semaphore,
    timeout: float,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> T:
    """Execute function with retry logic for transient failures."""
    last_exception: Exception | None = None
    func_name = func.__name__

    for attempt in range(1, MCP_CONNECTION_RETRY_ATTEMPTS + 1):
        try:
            return await _execute_single_attempt(func, semaphore, timeout, args, kwargs)
        except Exception as e:
            _, last_exception = await _handle_retry_exception(
                func_name, timeout, attempt, e, last_exception
            )

    if last_exception:
        raise RuntimeError(
            f"MCP tool {func_name} failed after {MCP_CONNECTION_RETRY_ATTEMPTS} attempts"
        ) from last_exception

    raise RuntimeError(f"MCP tool {func_name} failed unexpectedly")


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
    return await _execute_with_retry(func, semaphore, timeout, args, kwargs)


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


async def execute_tool_with_stability(
    func: Callable[..., Awaitable[T]],
    *args: object,
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    **kwargs: object,
) -> T:
    """Execute MCP tool function with stability protections.

    This is a convenience wrapper for tool execution that provides:
    - Timeout protection (prevents hanging operations)
    - Resource limit enforcement (concurrent operations)
    - Connection error handling
    - Automatic retry for transient failures

    Args:
        func: Async function to execute (the tool's business logic)
        *args: Positional arguments for func
        timeout: Maximum execution time in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result from func execution

    Raises:
        TimeoutError: If operation exceeds timeout
        RuntimeError: If resource limits exceeded or connection fails
    """
    return await with_mcp_stability(func, *args, timeout=timeout, **kwargs)


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
