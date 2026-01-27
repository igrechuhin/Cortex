"""Helper functions for synapse_tools module."""

from pathlib import Path
from typing import cast

from cortex.core.models import JsonDict, JsonValue, ModelDict
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.rules_manager import RulesManager
from cortex.tools.models import RulesExecutionResult


def format_rules_list(rules: list[ModelDict]) -> list[ModelDict]:
    """Format a list of rule objects into dictionaries."""
    result: list[ModelDict] = []
    for rule in rules:
        result.append(
            {
                "file": rule.get("file"),
                "tokens": rule.get("tokens"),
                "priority": rule.get("priority"),
                "relevance_score": rule.get("relevance_score"),
            }
        )
    return result


def format_language_rules_list(rules: list[ModelDict]) -> list[ModelDict]:
    """Format a list of language rule objects into dictionaries."""
    result: list[ModelDict] = []
    for rule in rules:
        result.append(
            {
                "file": rule.get("file"),
                "category": rule.get("category"),
                "tokens": rule.get("tokens"),
                "priority": rule.get("priority"),
                "relevance_score": rule.get("relevance_score"),
            }
        )
    return result


def _create_error_result(error_message: str) -> RulesExecutionResult:
    """Create error result for rules execution."""
    return RulesExecutionResult(
        status="error",
        task_description=None,
        context=None,
        rules_loaded=None,
        total_tokens=None,
        token_budget=None,
        source=None,
        error=error_message,
    )


async def execute_rules_with_context(
    task_description: str,
    max_tokens: int,
    min_relevance_score: float,
    project_files: str | None,
    rule_priority: str,
    context_aware: bool,
) -> RulesExecutionResult:
    """Execute rules with context workflow."""
    project_root = get_project_root()
    managers = await get_managers(project_root)

    validation_error = validate_rules_manager(managers)
    if validation_error:
        error_raw = validation_error.get("error")
        error_message = str(error_raw) if error_raw is not None else "Unknown error"
        return _create_error_result(error_message)

    rules_manager = await get_manager(managers, "rules_manager", RulesManager)
    file_paths = parse_project_files(project_files)

    result = await rules_manager.get_relevant_rules(
        task_description=task_description,
        max_tokens=max_tokens,
        min_relevance_score=min_relevance_score,
        project_files=file_paths,
        rule_priority=rule_priority,
        context_aware=context_aware,
    )

    return format_rules_response(result, task_description, max_tokens)


def validate_rules_manager(managers: ManagersDict) -> ModelDict | None:
    """Validate rules manager exists."""
    if getattr(managers, "rules_manager", None) is None:
        return {
            "status": "error",
            "error": (
                "Rules manager not initialized. Enable rules in " "configuration first."
            ),
        }
    return None


def parse_project_files(project_files: str | None) -> list[Path] | None:
    """Parse project files string into list of paths."""
    if not project_files:
        return None
    return [Path(f.strip()) for f in project_files.split(",") if f.strip()]


def _build_rules_loaded_data(result: ModelDict) -> ModelDict:
    """Build rules loaded data dictionary."""
    generic_rules = extract_and_format_rules(result, "generic_rules")
    language_rules = format_language_rules_list(
        extract_rules_list(result, "language_rules")
    )
    local_rules = extract_and_format_rules(result, "local_rules")
    return {
        "generic": cast(JsonValue, _to_json_list(generic_rules)),
        "language": cast(JsonValue, _to_json_list(language_rules)),
        "local": cast(JsonValue, _to_json_list(local_rules)),
    }


def format_rules_response(
    result: ModelDict, task_description: str, max_tokens: int
) -> RulesExecutionResult:
    """Format rules response model."""
    context_raw: JsonValue = result.get("context", {})
    context = (
        JsonDict.from_dict(cast(ModelDict, context_raw))
        if isinstance(context_raw, dict)
        else JsonDict()
    )

    rules_loaded_data = _build_rules_loaded_data(result)

    total_tokens_raw: JsonValue = result.get("total_tokens", 0)
    total_tokens = int(total_tokens_raw) if isinstance(total_tokens_raw, int) else 0
    source_raw: JsonValue = result.get("source", "local_only")
    source = str(source_raw) if source_raw is not None else "local_only"

    return RulesExecutionResult(
        status="success",
        task_description=task_description,
        context=context,
        rules_loaded=JsonDict.from_dict(rules_loaded_data),
        total_tokens=total_tokens,
        token_budget=max_tokens,
        source=source,
        error=None,
    )


def extract_rules_list(result: ModelDict, key: str) -> list[ModelDict]:
    """Extract rules list from result dictionary."""
    rules_raw = result.get(key, [])
    if isinstance(rules_raw, list):
        return [cast(ModelDict, item) for item in rules_raw if isinstance(item, dict)]
    return []


def extract_and_format_rules(result: ModelDict, key: str) -> list[ModelDict]:
    """Extract and format rules list."""
    rules_list = extract_rules_list(result, key)
    return format_rules_list(rules_list)


def _to_json_list(items: list[ModelDict]) -> list[JsonValue]:
    """Convert list of ModelDict to list of JsonValue."""
    return [cast(JsonValue, item) for item in items]
