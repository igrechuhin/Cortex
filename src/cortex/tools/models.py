"""
Pydantic Models for MCP Tool Return Types

This module re-exports Pydantic models for all Cortex MCP tool return types from
domain-specific submodules, enabling FastMCP 2.0 structured output with better
schema generation, automatic validation, and improved IDE support.

All models follow Pydantic v2 best practices. See submodules for definitions:
- file_operations_models: manage_file, rollback_file_version, manager init
- structure_models: check_structure_health, get_structure_info
- rules_models: rules index, get_relevant
- quality_precommit_models: execute_pre_commit_checks, fix_quality, preflight, etc.
- synapse_models: get_synapse_prompts, sync_synapse, fix_roadmap_corruption, etc.
- feedback_models: provide_feedback
- markdown_models: fix_markdown_lint
- health_connection_models: check_mcp_connection_health
- links_models: parse_file_links
- context_analysis_models: context usage, insights, cleanup report, etc.
- roadmap_operations_models: add/remove roadmap entry, append progress/activeContext
"""

from __future__ import annotations

# Re-export ManagersDict for convenience
from cortex.validation.models import (
    AllFilesTimestampResult,
    InfrastructureValidationResultModel,
    SingleFileTimestampResult,
)

from .models_reexports import *  # noqa: F403
from .models_reexports import __all__
from .validation_result_models import (
    ValidateDuplicationsResult,
    ValidateErrorResult,
    ValidateInfrastructureResult,
    ValidateQualityAllResult,
    ValidateQualitySingleResult,
    ValidateRoadmapSyncResult,
    ValidateSchemaAllResult,
    ValidateSchemaSingleResult,
    ValidateTimestampsResult,
)

# Union type for validate return (includes validation module models)
ValidateResult = (
    ValidateSchemaSingleResult
    | ValidateSchemaAllResult
    | ValidateDuplicationsResult
    | ValidateQualitySingleResult
    | ValidateQualityAllResult
    | ValidateInfrastructureResult
    | ValidateTimestampsResult
    | ValidateRoadmapSyncResult
    | ValidateErrorResult
    | SingleFileTimestampResult
    | AllFilesTimestampResult
    | InfrastructureValidationResultModel
)

# Re-exports: reference so type checker treats imports as used (reportUnusedImport)
_REEXPORTS = tuple(globals()[n] for n in __all__ if n in globals())
