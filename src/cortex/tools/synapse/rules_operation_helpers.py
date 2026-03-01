"""Helper functions for rules operations."""

import json
from enum import Enum
from typing import cast

from cortex.core.models import ModelDict
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.models import RulesManagerStatusModel
from cortex.tools.error_formatters import (
    format_invalid_parameter_error,
    format_missing_parameter_error,
)


class RulesOperation(str, Enum):
    """Fixed set of rules tool operations. Use instead of raw strings."""

    INDEX = "index"
    GET_RELEVANT = "get_relevant"


def parse_rules_operation(value: str | None) -> RulesOperation | None:
    """Parse string to RulesOperation. Returns None if invalid or missing."""
    if value is None:
        return None
    try:
        return RulesOperation(value)
    except ValueError:
        return None


def resolve_config_defaults(
    optimization_config: OptimizationConfig,
    max_tokens: int | None,
    min_relevance_score: float | None,
) -> tuple[int, float]:
    """Resolve configuration defaults for get_relevant operation.

    Args:
        optimization_config: Optimization configuration
        max_tokens: Maximum tokens for rules (optional)
        min_relevance_score: Minimum relevance score (optional)

    Returns:
        Tuple of (max_tokens, min_relevance_score) with defaults applied
    """
    resolved_max_tokens = (
        max_tokens
        if max_tokens is not None
        else optimization_config.get_rules_max_tokens()
    )
    resolved_min_score = (
        min_relevance_score
        if min_relevance_score is not None
        else optimization_config.get_rules_min_relevance()
    )
    return resolved_max_tokens, resolved_min_score


def extract_all_rules(
    relevant_rules: ModelDict,
) -> list[ModelDict]:
    """Extract all rules from the relevant rules payload.

    Args:
        relevant_rules: Rules result model containing rules by category

    Returns:
        List of all rules combined from all categories
    """
    all_rules: list[ModelDict] = []
    generic_rules = relevant_rules.get("generic_rules", [])
    language_rules = relevant_rules.get("language_rules", [])
    local_rules = relevant_rules.get("local_rules", [])
    if isinstance(generic_rules, list):
        all_rules.extend([r for r in generic_rules if isinstance(r, dict)])
    if isinstance(language_rules, list):
        all_rules.extend([r for r in language_rules if isinstance(r, dict)])
    if isinstance(local_rules, list):
        all_rules.extend([r for r in local_rules if isinstance(r, dict)])
    return all_rules


def calculate_total_tokens(
    relevant_rules: ModelDict, all_rules: list[ModelDict]
) -> int:
    """Calculate total tokens from rules.

    Args:
        relevant_rules: Rules result model containing total_tokens
        all_rules: List of all rules

    Returns:
        Total tokens count
    """
    total_tokens = relevant_rules.get("total_tokens")
    if isinstance(total_tokens, int) and total_tokens > 0:
        return total_tokens

    computed = 0
    for rule in all_rules:
        tokens = rule.get("tokens")
        if isinstance(tokens, int):
            computed += tokens
        elif isinstance(tokens, float):
            computed += int(tokens)
    return computed


def build_get_relevant_response(
    task_description: str,
    max_tokens: int,
    min_score: float,
    all_rules: list[ModelDict],
    total_tokens: int,
    status: RulesManagerStatusModel,
    relevant_rules: ModelDict,
) -> str:
    """Build response for get_relevant operation."""
    status_payload = cast(ModelDict, status.model_dump(mode="json"))
    return json.dumps(
        {
            "status": "success",
            "operation": "get_relevant",
            "task_description": task_description,
            "max_tokens": max_tokens,
            "min_relevance_score": min_score,
            "rules_count": len(all_rules),
            "total_tokens": total_tokens,
            "rules": all_rules,
            "rules_manager_status": status_payload,
            "rules_context": relevant_rules.get("context"),
            "rules_source": relevant_rules.get("source"),
        },
        indent=2,
    )


def build_invalid_operation_error(operation: str) -> str:
    """Build error response for invalid operation."""
    valid_operations = [op.value for op in RulesOperation]
    return format_invalid_parameter_error(
        parameter_name="operation",
        invalid_value=operation,
        valid_options=valid_operations,
        tool_name="rules",
    )


def build_missing_rules_parameters_error() -> str:
    """Build error response for missing operation parameter."""
    return format_missing_parameter_error(
        missing_parameters=["operation"],
        tool_name="rules",
        example={"operation": "index"},
    )
