"""
Reorganization subpackage for MCP Memory Bank.

This package contains modules for planning and executing Memory Bank reorganization:
- analyzer: Structure analysis and category inference
- strategies: Optimization strategies and structure proposals
- executor: Action generation and impact calculation
"""

from cortex.refactoring.reorganization.analyzer import ReorganizationAnalyzer
from cortex.refactoring.reorganization.executor import ReorganizationExecutor
from cortex.refactoring.reorganization.strategies import (
    ReorganizationStrategies,
)

__all__ = [
    "ReorganizationAnalyzer",
    "ReorganizationStrategies",
    "ReorganizationExecutor",
]
