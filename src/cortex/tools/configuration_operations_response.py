"""Response helpers for configuration operations.

Extracted from configuration_operations to keep main module under 400 lines.
"""

import json
from typing import Protocol

from cortex.core.models import JsonValue, ModelDict
from cortex.refactoring.learning_engine import LearningEngine
from cortex.tools.models import LearnedPatternsResult


class ConfigProtocol(Protocol):
    """Protocol for configuration objects with set method.

    Supports both ValidationConfig/AdaptationConfig (set(key, value) -> None)
    and OptimizationConfig (set(key_path, value) -> bool) patterns.
    """

    def set(self, __key_or_path: str, __value: JsonValue) -> None | bool:
        """Set configuration value."""
        ...


def apply_config_updates(
    config: ConfigProtocol,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str | None:
    """Apply configuration updates. Returns error message if invalid,
    None on success."""
    if settings:
        for k, v in settings.items():
            _ = config.set(k, v)
        return None
    elif key and value is not None:
        _ = config.set(key, value)
        return None
    else:
        return json.dumps(
            {
                "status": "error",
                "error": "Either settings or key+value required for update",
            },
            indent=2,
        )


def create_success_response(
    component: str, configuration: ModelDict, message: str | None
) -> str:
    """Create a success response with configuration."""
    response: ModelDict = {
        "status": "success",
        "component": component,
        "configuration": configuration,
    }
    if message:
        response["message"] = message
    return json.dumps(response, indent=2)


def get_learned_patterns(learning_engine: LearningEngine) -> LearnedPatternsResult:
    """Get all learned patterns as model."""
    from cortex.core.models import JsonDict

    patterns_dict = learning_engine.data_manager.get_all_patterns()
    return LearnedPatternsResult(
        patterns={
            pattern_id: JsonDict.from_dict(pattern.to_dict())
            for pattern_id, pattern in patterns_dict.items()
        }
    )


def export_learned_patterns(learning_engine: LearningEngine) -> str:
    """Export learned patterns as JSON response."""
    patterns = get_learned_patterns(learning_engine)
    return json.dumps(
        {
            "status": "success",
            "component": "learning",
            "action": "export_patterns",
            "patterns": {
                k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                for k, v in patterns.patterns.items()
            },
        },
        indent=2,
    )
