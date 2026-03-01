"""Plan and roadmap operations.

Subpackage for plan CRUD, plan completion, roadmap entry management,
roadmap corruption fixing, and related tools.
"""

# Import for side-effect registration (MCP tools)
from . import (
    completion,
    corruption,
    entries,
    operations,
    plan,
    register,
    roadmap,
)

__all__ = [
    "completion",
    "corruption",
    "entries",
    "operations",
    "plan",
    "roadmap",
    "register",
]
