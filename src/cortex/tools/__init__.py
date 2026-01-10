"""
Tools Package

This package contains all MCP tool implementations organized by phase.

Modules:
- file_operations: File management operations (1 tool) - Phase 9.1.1 split
- validation_operations: Validation operations (1 tool) - Phase 9.1.1 split
- analysis_operations: Analysis operations (2 tools) - Phase 9.1.1 split
- rules_operations: Rules management (1 tool) - Phase 9.1.1 split
- configuration_operations: Configuration management (1 tool) - Phase 9.1.1 split
- phase1_foundation: Core Memory Bank operations (10 tools)
- phase2_linking: Link management and transclusion (4 tools)
- phase3_validation: Validation and quality checks (5 tools)
- phase4_optimization: Token optimization and context management (7 tools)
- phase5_analysis: Usage pattern and structure analysis (3 tools)
- phase5_refactoring: Refactoring suggestions (4 tools)
- phase5_execution: Safe execution and learning (6 tools)
- phase6_shared_rules: Shared rules repository (4 tools)
- phase8_structure: Project structure management (6 tools)

Total: 52 tools (Phase 7.10 consolidation + Phase 9.1.1 split)
"""

# Import all tool modules to register their decorators
from . import (
    analysis_operations,  # noqa: F401
    configuration_operations,  # noqa: F401
    file_operations,  # noqa: F401
    phase1_foundation,  # noqa: F401
    phase2_linking,  # noqa: F401
    phase3_validation,  # noqa: F401
    phase4_optimization,  # noqa: F401
    phase5_analysis,  # noqa: F401
    phase5_execution,  # noqa: F401
    phase5_refactoring,  # noqa: F401
    phase6_shared_rules,  # noqa: F401
    phase8_structure,  # noqa: F401
    rules_operations,  # noqa: F401
    validation_operations,  # noqa: F401
)

__all__ = [
    "analysis_operations",
    "configuration_operations",
    "file_operations",
    "phase1_foundation",
    "phase2_linking",
    "phase3_validation",
    "phase4_optimization",
    "phase5_analysis",
    "phase5_refactoring",
    "phase5_execution",
    "phase6_shared_rules",
    "phase8_structure",
    "rules_operations",
    "validation_operations",
]
