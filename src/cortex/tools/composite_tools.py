"""Backward-compat shim: composite_tools moved to execution/ (Session 18)."""

from cortex.tools.execution.composite_tools import (  # noqa: F401
    run_composite_workflow,
)

__all__ = ["run_composite_workflow"]
