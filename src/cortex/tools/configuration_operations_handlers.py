"""Component handlers for configuration operations.

Extracted from configuration_operations to keep main module under 400 lines.
"""

import json
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.learning_engine import LearningEngine
from cortex.tools.configuration_helpers import ConfigAction
from cortex.tools.configuration_operations_errors import create_invalid_action_error
from cortex.tools.configuration_operations_response import (
    apply_config_updates,
    create_success_response,
    export_learned_patterns,
    get_learned_patterns,
)
from cortex.validation.validation_config import ValidationConfig


async def configure_validation(
    mgrs: ManagersDict,
    action: ConfigAction,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure validation settings."""
    validation_config = await get_manager(mgrs, "validation_config", ValidationConfig)

    if action == ConfigAction.VIEW:
        validation_dict = cast(
            ModelDict, validation_config.config.model_dump(mode="json")
        )
        return create_success_response("validation", validation_dict, message=None)
    elif action == ConfigAction.UPDATE:
        return await handle_validation_update(validation_config, settings, key, value)
    elif action == ConfigAction.RESET:
        return await handle_validation_reset(validation_config)
    else:
        return create_invalid_action_error(action.value)


async def handle_validation_update(
    validation_config: ValidationConfig,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Handle validation configuration update."""
    error = apply_config_updates(validation_config, settings, key, value)
    if error:
        return error
    await validation_config.save()
    validation_dict = cast(ModelDict, validation_config.config.model_dump(mode="json"))
    return create_success_response(
        "validation", validation_dict, "Configuration updated"
    )


async def handle_validation_reset(validation_config: ValidationConfig) -> str:
    """Handle validation configuration reset."""
    validation_config.reset_to_defaults()
    await validation_config.save()
    validation_dict = cast(ModelDict, validation_config.config.model_dump(mode="json"))
    return create_success_response(
        "validation", validation_dict, "Configuration reset to defaults"
    )


async def configure_optimization(
    mgrs: ManagersDict,
    action: ConfigAction,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure optimization settings."""
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )

    if action == ConfigAction.VIEW:
        return create_success_response(
            "optimization", optimization_config.to_dict(), message=None
        )
    elif action == ConfigAction.UPDATE:
        return await handle_optimization_update(
            optimization_config, settings, key, value
        )
    elif action == ConfigAction.RESET:
        return await handle_optimization_reset(optimization_config)
    else:
        return create_invalid_action_error(action.value)


async def handle_optimization_update(
    optimization_config: OptimizationConfig,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Handle optimization configuration update."""
    error = apply_config_updates(optimization_config, settings, key, value)
    if error:
        return error
    _ = await optimization_config.save_config()
    return create_success_response(
        "optimization", optimization_config.to_dict(), "Configuration updated"
    )


async def handle_optimization_reset(
    optimization_config: OptimizationConfig,
) -> str:
    """Handle optimization configuration reset."""
    await optimization_config.reset()
    return create_success_response(
        "optimization",
        optimization_config.to_dict(),
        "Configuration reset to defaults",
    )


async def _initialize_learning_components(
    mgrs: ManagersDict,
) -> tuple[LearningEngine, OptimizationConfig, AdaptationConfig]:
    """Initialize learning-related components."""
    learning_engine = await get_manager(mgrs, "learning_engine", LearningEngine)
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )
    adaptation_config = AdaptationConfig(base_config=optimization_config.config)
    return learning_engine, optimization_config, adaptation_config


async def configure_learning(
    mgrs: ManagersDict,
    action: ConfigAction,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure learning settings."""
    (
        learning_engine,
        optimization_config,
        adaptation_config,
    ) = await _initialize_learning_components(mgrs)

    if action == ConfigAction.VIEW:
        return handle_learning_view(learning_engine, adaptation_config)
    elif action == ConfigAction.UPDATE:
        return await handle_learning_update(
            learning_engine,
            optimization_config,
            adaptation_config,
            settings,
            key,
            value,
        )
    elif action == ConfigAction.RESET:
        return await handle_learning_reset(
            learning_engine, optimization_config, adaptation_config
        )
    else:
        return create_invalid_action_error(action.value)


def handle_learning_view(
    learning_engine: LearningEngine, adaptation_config: AdaptationConfig
) -> str:
    """Handle learning configuration view."""
    patterns = get_learned_patterns(learning_engine)
    return json.dumps(
        {
            "status": "success",
            "component": "learning",
            "configuration": adaptation_config.to_dict(),
            "learned_patterns": {
                k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                for k, v in patterns.patterns.items()
            },
        },
        indent=2,
    )


async def handle_learning_update(
    learning_engine: LearningEngine,
    optimization_config: OptimizationConfig,
    adaptation_config: AdaptationConfig,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Handle learning configuration update."""
    if key == "export_patterns":
        return export_learned_patterns(learning_engine)

    error = apply_config_updates(adaptation_config, settings, key, value)
    if error:
        return error
    _ = await optimization_config.save_config()
    return create_success_response(
        "learning", adaptation_config.to_dict(), "Configuration updated"
    )


async def handle_learning_reset(
    learning_engine: LearningEngine,
    optimization_config: OptimizationConfig,
    adaptation_config: AdaptationConfig,
) -> str:
    """Handle learning configuration reset."""
    _ = await learning_engine.reset_learning_data()
    adaptation_config.reset_to_defaults()
    _ = await optimization_config.save_config()
    return json.dumps(
        {
            "status": "success",
            "message": "Learning data and configuration reset to defaults",
            "configuration": adaptation_config.to_dict(),
        },
        indent=2,
    )
