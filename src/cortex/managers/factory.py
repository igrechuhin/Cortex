#!/usr/bin/env python3
# ruff: noqa: I001
"""Manager factory functions for creating and registering managers."""

from cortex.managers.factory_analysis import add_analysis_managers
from cortex.managers.factory_execution import add_execution_managers
from cortex.managers.factory_linking import add_linking_managers
from cortex.managers.factory_optimization import add_optimization_managers
from cortex.managers.factory_refactoring import add_refactoring_managers
from cortex.managers.factory_usage import add_usage_tracker
from cortex.managers.factory_validation import add_validation_managers

__all__ = [
    "add_analysis_managers",
    "add_execution_managers",
    "add_linking_managers",
    "add_optimization_managers",
    "add_refactoring_managers",
    "add_usage_tracker",
    "add_validation_managers",
]
