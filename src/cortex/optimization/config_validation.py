"""
Validation of optimization configuration dicts.

Validates token_budget, loading_strategy, summarization, and relevance weights.
"""

from cortex.core.models import JsonValue, ModelDict


def _get(
    config: ModelDict, key_path: str, default: JsonValue | None = None
) -> JsonValue:
    """Get value from config using dot notation."""
    value: JsonValue = config
    for key in key_path.split("."):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def _validate_token_budget(config: ModelDict) -> str | None:
    """Validate token budget configuration."""
    default_budget = _get(config, "token_budget.default_budget")
    max_budget = _get(config, "token_budget.max_budget")
    if not isinstance(default_budget, int) or default_budget <= 0:
        return "token_budget.default_budget must be a positive integer"
    if not isinstance(max_budget, int) or max_budget <= 0:
        return "token_budget.max_budget must be a positive integer"
    if default_budget > max_budget:
        return "token_budget.default_budget cannot exceed max_budget"
    return None


def _validate_max_response_tokens(config: ModelDict) -> str | None:
    """Validate max response token limit."""
    max_response_tokens = _get(config, "max_response_tokens", 50000)
    if not isinstance(max_response_tokens, int) or max_response_tokens <= 0:
        return "max_response_tokens must be a positive integer"
    return None


def _validate_loading_strategy(config: ModelDict) -> str | None:
    """Validate loading strategy configuration."""
    strategy = _get(config, "loading_strategy.default", "dependency_aware")
    valid = ["priority", "dependency_aware", "section_level", "hybrid"]
    if not isinstance(strategy, str) or strategy not in valid:
        return f"loading_strategy.default must be one of: {', '.join(valid)}"
    return None


def _validate_summarization(config: ModelDict) -> str | None:
    """Validate summarization configuration."""
    target_reduction = _get(config, "summarization.target_reduction", 0.5)
    if not isinstance(target_reduction, (int, float)) or not (
        0 < float(target_reduction) < 1
    ):
        return "summarization.target_reduction must be between 0 and 1"
    return None


def _validate_relevance_weights(config: ModelDict) -> str | None:
    """Validate relevance weights sum to ~1.0."""
    rel = config.get("relevance")
    if not isinstance(rel, dict):
        return "relevance section must be a dict"
    kw = rel.get("keyword_weight", 0.4)
    dep = rel.get("dependency_weight", 0.3)
    rec = rel.get("recency_weight", 0.2)
    qual = rel.get("quality_weight", 0.1)
    total = (
        (float(kw) if isinstance(kw, (int, float)) else 0.4)
        + (float(dep) if isinstance(dep, (int, float)) else 0.3)
        + (float(rec) if isinstance(rec, (int, float)) else 0.2)
        + (float(qual) if isinstance(qual, (int, float)) else 0.1)
    )
    if not 0.9 <= total <= 1.1:
        return f"relevance weights must sum to ~1.0 (got {total})"
    return None


def validate_optimization_config(config: ModelDict) -> tuple[bool, str | None]:
    """
    Validate optimization configuration dict.

    Returns:
        Tuple of (is_valid, error_message).
    """
    err = _validate_token_budget(config)
    if err:
        return False, err
    err = _validate_max_response_tokens(config)
    if err:
        return False, err
    err = _validate_loading_strategy(config)
    if err:
        return False, err
    err = _validate_summarization(config)
    if err:
        return False, err
    err = _validate_relevance_weights(config)
    if err:
        return False, err
    return True, None
