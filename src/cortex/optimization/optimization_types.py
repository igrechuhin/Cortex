"""
Types for optimization strategies.

This module contains shared types used across optimization strategy modules.
"""

from cortex.optimization.models import OptimizationResultModel

# Use Pydantic model - alias for backward compatibility
OptimizationResult = OptimizationResultModel
