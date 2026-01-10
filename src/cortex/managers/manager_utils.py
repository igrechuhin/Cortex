"""Helper utilities for lazy manager initialization."""

from typing import TypeVar, cast

from cortex.managers.lazy_manager import LazyManager

T = TypeVar("T")


async def get_manager(managers: dict[str, object], name: str, type_: type[T]) -> T:
    """Get manager from dict, unwrapping LazyManager if needed.

    Args:
        managers: Manager dict from get_managers()
        name: Manager name
        type_: Expected manager type

    Returns:
        Manager instance of specified type
    """
    manager_or_lazy = managers[name]

    if isinstance(manager_or_lazy, LazyManager):
        manager = cast(T, await manager_or_lazy.get())
    else:
        manager = cast(T, manager_or_lazy)

    return manager
