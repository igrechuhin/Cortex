"""Helper utilities for lazy manager initialization."""

from typing import cast

from cortex.core.models import ModelDict
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import ManagersDict


async def get_manager[T](
    managers: ManagersDict | ModelDict | ManagersBuilder, name: str, type_: type[T]
) -> T:
    """Get manager from dict or ManagersDict, unwrapping LazyManager if needed.

    Args:
        managers: Manager dict from get_managers(), ManagersDict model, or builder dict
        name: Manager name
        type_: Expected manager type

    Returns:
        Manager instance of specified type
    """
    # Handle Pydantic model by accessing attribute or using model_dump()
    if isinstance(managers, ManagersDict):
        manager_or_lazy = getattr(managers, name, None)
        if manager_or_lazy is None:
            # Fallback to dict access if attribute not found
            managers_dict = managers.model_dump()
            manager_or_lazy = managers_dict.get(name)
    else:
        manager_or_lazy = managers[name]

    if isinstance(manager_or_lazy, LazyManager):
        manager = cast(T, await manager_or_lazy.get())
    else:
        manager = cast(T, manager_or_lazy)

    return manager
