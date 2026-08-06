"""
Rules Operations - Operation Handlers

Handlers for index and get_relevant operations.
"""

import json

from cortex.core.models import ModelDict, OperationStatus
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.models import RulesManagerStatusModel
from cortex.optimization.rules_manager import RulesManager
from cortex.tools.synapse.rules_operation_helpers import (
    RulesOperation,
    build_diagnostics_response,
    build_get_relevant_response,
    build_invalid_operation_error,
    calculate_total_tokens,
    extract_all_rules,
    resolve_config_defaults,
)
from cortex.tools.synapse.rules_operations_validation import (
    validate_rules_folder_config,
    validate_rules_folder_exists,
)


async def check_rules_enabled(
    optimization_config: OptimizationConfig,
) -> str | None:
    """Check if rules indexing is enabled.

    Args:
        optimization_config: Optimization configuration

    Returns:
        JSON error message if disabled, None if enabled
    """
    if not optimization_config.is_rules_enabled():
        return json.dumps(
            {
                "status": "disabled",
                "message": (
                    "Rules indexing is disabled. "
                    "Enable it in .cortex/config/optimization.json"
                ),
            },
            indent=2,
        )
    return None


def _format_rules_index_error_response(
    result_payload: ModelDict, rules_folder: str
) -> str:
    from cortex.tools.execution.error_formatters import format_tool_error

    error_msg = result_payload.get("error", "Unknown error")
    return format_tool_error(
        FileNotFoundError(str(error_msg)),
        suggestion=(
            "Create the rules folder at the configured path or update "
            "rules.rules_folder in .cortex/config/optimization.json "
            "to point to an existing directory."
        ),
        example={"rules": {"enabled": True, "rules_folder": ".cortex/rules"}},
        context={
            "configured_path": rules_folder,
            "config_path": ".cortex/config/optimization.json",
        },
    )


async def handle_index_operation(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    force: bool,
) -> str:
    """Handle index operation.

    Args:
        rules_manager: Rules manager instance
        optimization_config: Optimization configuration
        force: Force reindexing even if recently indexed

    Returns:
        JSON string with index result
    """
    rules_folder, config_error = validate_rules_folder_config(optimization_config)
    if config_error:
        return config_error
    assert rules_folder is not None

    result = await rules_manager.index_rules(force=force)
    result_payload: ModelDict = result

    if result_payload.get("status") == "error":
        return _format_rules_index_error_response(result_payload, rules_folder)

    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "operation": "index",
            "result": result_payload,
        },
        indent=2,
    )


async def validate_get_relevant_params(task_description: str | None) -> str | None:
    """Validate parameters for get_relevant operation.

    Args:
        task_description: Description of the task

    Returns:
        JSON error message if validation fails, None if valid
    """
    if not task_description:
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": "task_description is required for get_relevant operation",
            },
            indent=2,
        )
    return None


async def _fetch_relevant_rules(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    task_description: str,
    resolved_max_tokens: int,
    resolved_min_score: float,
) -> ModelDict:
    """Fetch relevant rules from rules manager."""
    rule_priority = optimization_config.get_rule_priority()
    context_aware = optimization_config.is_context_aware_loading()

    relevant_rules = await rules_manager.get_relevant_rules(
        task_description=task_description,
        max_tokens=resolved_max_tokens,
        min_relevance_score=resolved_min_score,
        rule_priority=rule_priority,
        context_aware=context_aware,
    )
    return relevant_rules


def _build_status_from_config(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    rules_folder: str | None,
) -> RulesManagerStatusModel:
    """Build status from current optimization config."""
    indexer_status = rules_manager.indexer.get_status()

    return RulesManagerStatusModel(
        enabled=rules_folder is not None,
        rules_folder=rules_folder,
        indexed_files=indexer_status.indexed_files,
        last_indexed=indexer_status.last_indexed,
        auto_reindex_enabled=indexer_status.auto_reindex_enabled,
        reindex_interval_minutes=optimization_config.get_rules_reindex_interval(),
        total_tokens=indexer_status.total_tokens,
    )


async def _execute_get_relevant(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    task_description: str,
    max_tokens: int | None,
    min_relevance_score: float | None,
    rules_folder: str,
) -> str:
    """Execute get_relevant operation after validation."""
    resolved_max_tokens, resolved_min_score = resolve_config_defaults(
        optimization_config, max_tokens, min_relevance_score
    )
    relevant_rules_dict = await _fetch_relevant_rules(
        rules_manager,
        optimization_config,
        task_description,
        resolved_max_tokens,
        resolved_min_score,
    )
    all_rules = extract_all_rules(relevant_rules_dict)
    total_tokens = calculate_total_tokens(relevant_rules_dict, all_rules)
    status = _build_status_from_config(rules_manager, optimization_config, rules_folder)
    return build_get_relevant_response(
        task_description,
        resolved_max_tokens,
        resolved_min_score,
        all_rules,
        total_tokens,
        status,
        relevant_rules_dict,
    )


async def handle_get_relevant_operation(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    task_description: str,
    max_tokens: int | None,
    min_relevance_score: float | None,
) -> str:
    """Handle get_relevant operation."""
    rules_folder, config_error = validate_rules_folder_config(optimization_config)
    if config_error:
        return config_error
    assert rules_folder is not None

    folder_error = validate_rules_folder_exists(rules_manager, rules_folder)
    if folder_error:
        return folder_error

    return await _execute_get_relevant(
        rules_manager,
        optimization_config,
        task_description,
        max_tokens,
        min_relevance_score,
        rules_folder,
    )


async def handle_diagnostics_operation(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
) -> str:
    """Handle the explicit diagnostics operation (volatile fields included)."""
    rules_folder, _config_error = validate_rules_folder_config(optimization_config)
    status = _build_status_from_config(rules_manager, optimization_config, rules_folder)
    return build_diagnostics_response(status)


async def dispatch_operation(
    operation: RulesOperation,
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    force: bool,
    task_description: str | None,
    max_tokens: int | None,
    min_relevance_score: float | None,
) -> str:
    """Dispatch to appropriate operation handler."""
    if operation == RulesOperation.INDEX:
        return await handle_index_operation(rules_manager, optimization_config, force)
    if operation == RulesOperation.DIAGNOSTICS:
        return await handle_diagnostics_operation(rules_manager, optimization_config)
    if operation == RulesOperation.GET_RELEVANT:
        if error_msg := await validate_get_relevant_params(task_description):
            return error_msg
        assert task_description is not None
        return await handle_get_relevant_operation(
            rules_manager,
            optimization_config,
            task_description,
            max_tokens,
            min_relevance_score,
        )
    return build_invalid_operation_error(operation.value)
