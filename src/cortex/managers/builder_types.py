"""Types used during manager initialization.

This module intentionally contains only lightweight type aliases / protocols to
avoid circular imports between manager initialization code and helper utilities.
"""

from typing import Protocol


class ManagerBuilderValue(Protocol):
    """Marker protocol for heterogeneous manager values during initialization."""


ManagersBuilder = dict[str, ManagerBuilderValue]
