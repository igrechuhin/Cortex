"""
Rules Operations - Validation Helpers

Validation logic for rules folder configuration and existence.
"""

from cortex.optimization.config import OptimizationConfig
from cortex.optimization.rules_manager import RulesManager


def validate_rules_folder_config(
    optimization_config: OptimizationConfig,
) -> tuple[str | None, str | None]:
    """Validate rules folder configuration.

    Args:
        optimization_config: Optimization configuration

    Returns:
        Tuple of (rules_folder, error_message). If error_message is not None,
        rules_folder is None and error_message contains the formatted error.
    """
    rules_folder = optimization_config.get_rules_folder()
    if not rules_folder:
        from cortex.tools.execution.error_formatters import format_tool_error

        error = format_tool_error(
            ValueError("Rules folder not configured"),
            suggestion=(
                "Configure rules_folder in .cortex/config/optimization.json "
                "under 'rules.rules_folder'. Example: '.cortex/rules'"
            ),
            example={"rules": {"enabled": True, "rules_folder": ".cortex/rules"}},
            context={"config_path": ".cortex/config/optimization.json"},
        )
        return None, error
    return rules_folder, None


def validate_rules_folder_exists(
    rules_manager: RulesManager, rules_folder: str
) -> str | None:
    """Validate that rules folder exists on filesystem.

    Args:
        rules_manager: Rules manager instance
        rules_folder: Rules folder path from config

    Returns:
        Error message if folder doesn't exist, None if valid
    """
    project_root = rules_manager.project_root
    rules_path = project_root / rules_folder
    if not rules_path.exists():
        from cortex.tools.execution.error_formatters import format_tool_error

        return format_tool_error(
            FileNotFoundError(f"Rules folder not found: {rules_folder}"),
            suggestion=(
                f"Create the rules folder at '{rules_path}' or update "
                f"rules.rules_folder in .cortex/config/optimization.json "
                f"to point to an existing directory."
            ),
            example={"rules": {"enabled": True, "rules_folder": ".cortex/rules"}},
            context={
                "configured_path": rules_folder,
                "absolute_path": str(rules_path),
                "config_path": ".cortex/config/optimization.json",
            },
        )
    return None
