"""Retry utilities for transient failure handling.

Provides decorators and functions for automatic retry with exponential
backoff, suitable for file operations, network operations, and other
transient failure scenarios.
"""

import asyncio
import functools
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_SECONDS = 0.5
DEFAULT_MAX_DELAY_SECONDS = 10.0
DEFAULT_EXPONENTIAL_BASE = 2.0

# Transient exceptions that warrant retry
TRANSIENT_EXCEPTIONS = (
    OSError,  # File system errors
    TimeoutError,  # Timeout errors
    ConnectionError,  # Network errors
    BlockingIOError,  # Resource temporarily unavailable
)


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: object,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    exceptions: tuple[type[Exception], ...] = TRANSIENT_EXCEPTIONS,
    **kwargs: object,
) -> T:
    """Execute an async function with automatic retry on transient failures.

    Uses exponential backoff with jitter to prevent thundering herd.

    Args:
        func: Async function to execute.
        *args: Positional arguments for func.
        max_retries: Maximum number of retry attempts (default: 3).
        base_delay: Initial delay between retries in seconds (default: 0.5).
        max_delay: Maximum delay between retries in seconds (default: 10.0).
        exceptions: Tuple of exception types to retry on.
        **kwargs: Keyword arguments for func.

    Returns:
        Result of the function call.

    Raises:
        The last exception if all retries are exhausted.

    Example:
        ```python
        result = await retry_async(
            read_file, "path/to/file.md",
            max_retries=3, base_delay=0.5
        )
        ```
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                _log_retry_exhausted(func, max_retries, attempt, e)
                raise
            delay = _calculate_retry_delay(attempt, base_delay, max_delay)
            await _log_and_wait_retry(func, attempt, max_retries, delay, e)

    # Should not reach here, but satisfy type checker
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error")


def _log_retry_exhausted(
    func: Callable[..., object],
    max_retries: int,
    attempt: int,
    e: Exception,
) -> None:
    """Log retry exhaustion."""
    logger.error(
        f"Retry exhausted after {max_retries} attempts: {e}",
        extra={"function": func.__name__, "attempt": attempt},
    )


def _calculate_retry_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Calculate retry delay with exponential backoff and jitter."""
    delay = min(base_delay * (DEFAULT_EXPONENTIAL_BASE**attempt), max_delay)
    jitter = delay * 0.25 * (random.random() * 2 - 1)
    return max(0.1, delay + jitter)


async def _log_and_wait_retry(
    func: Callable[..., object],
    attempt: int,
    max_retries: int,
    delay: float,
    e: Exception,
) -> None:
    """Log retry attempt and wait."""
    logger.warning(
        f"Transient error, retrying in {delay:.2f}s "
        + f"(attempt {attempt + 1}/{max_retries}): {e}",
        extra={"function": func.__name__, "delay": delay},
    )
    await asyncio.sleep(delay)


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    exceptions: tuple[type[Exception], ...] = TRANSIENT_EXCEPTIONS,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for automatic retry on async functions.

    Args:
        max_retries: Maximum number of retry attempts (default: 3).
        base_delay: Initial delay between retries in seconds (default: 0.5).
        exceptions: Tuple of exception types to retry on.

    Returns:
        Decorator function.

    Example:
        ```python
        @with_retry(max_retries=3, base_delay=0.5)
        async def read_with_retry(path: str) -> str:
            async with aiofiles.open(path) as f:
                return await f.read()
        ```
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            async def call_func() -> T:
                return await func(*args, **kwargs)

            return await retry_async(
                call_func,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=DEFAULT_MAX_DELAY_SECONDS,
                exceptions=exceptions,
            )

        return wrapper

    return decorator
