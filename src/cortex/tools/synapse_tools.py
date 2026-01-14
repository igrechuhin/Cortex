"""
Synapse Tools for MCP Memory Bank.

This module contains tools for syncing, updating, and retrieving
shared rules and prompts from a git submodule-based Synapse repository.

Total: 5 tools
- sync_synapse
- update_synapse_rule
- get_synapse_rules
- get_synapse_prompts
- update_synapse_prompt

Note: setup_synapse has been replaced by a prompt template in docs/prompts/
"""

import json
from pathlib import Path
from typing import cast

from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.optimization.rules_manager import RulesManager
from cortex.rules.synapse_manager import SynapseManager
from cortex.server import mcp


def format_rules_list(rules: list[object]) -> list[dict[str, object]]:
    """Format a list of rule objects into dictionaries."""
    result: list[dict[str, object]] = []
    for r in rules:
        if isinstance(r, dict):
            r_dict: dict[str, object] = cast(dict[str, object], r)
            result.append(
                {
                    "file": r_dict.get("file"),
                    "tokens": r_dict.get("tokens"),
                    "priority": r_dict.get("priority"),
                    "relevance_score": r_dict.get("relevance_score"),
                }
            )
    return result


def format_language_rules_list(rules: list[object]) -> list[dict[str, object]]:
    """Format a list of language rule objects into dictionaries."""
    result: list[dict[str, object]] = []
    for r in rules:
        if isinstance(r, dict):
            rule_dict: dict[str, object] = cast(dict[str, object], r)
            result.append(
                {
                    "file": rule_dict.get("file"),
                    "category": rule_dict.get("category"),
                    "tokens": rule_dict.get("tokens"),
                    "priority": rule_dict.get("priority"),
                    "relevance_score": rule_dict.get("relevance_score"),
                }
            )
    return result


def format_prompts_list(prompts: list[dict[str, object]]) -> list[dict[str, object]]:
    """Format a list of prompt objects into dictionaries."""
    result: list[dict[str, object]] = []
    for p in prompts:
        result.append(
            {
                "file": p.get("file"),
                "name": p.get("name"),
                "category": p.get("category"),
                "description": p.get("description"),
                "keywords": p.get("keywords"),
            }
        )
    return result


@mcp.tool()
async def sync_synapse(pull: bool = True, push: bool = False) -> str:
    """
    Sync Synapse repository with remote using git operations.

    This tool synchronizes the local Synapse git submodule with the remote
    repository. When pulling, it fetches the latest rules and prompts from
    other projects that share the same Synapse repository. When pushing, it
    shares local modifications with all other projects. After pulling changes,
    the rules index is automatically rebuilt to incorporate new or modified rules.

    Args:
        pull: Pull latest changes from remote repository.
              Set to True to fetch updates from other projects.
              Triggers automatic rules reindexing if changes are detected.
              Default: True

        push: Push local changes to remote repository.
              Set to True to share your local modifications with other projects.
              Requires commit access to the Synapse repository.
              Default: False

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - pulled: Boolean indicating if pull was performed
        - pushed: Boolean indicating if push was performed
        - changes: Dictionary with lists of added/modified/deleted files
        - reindex_triggered: Boolean indicating if rules reindex occurred
        - last_sync: ISO timestamp of sync operation
        - error: Error message (only present if status is "error")

    Examples:
        Example 1: Pull latest changes from remote
        >>> await sync_synapse(pull=True, push=False)
        {
          "status": "success",
          "pulled": true,
          "pushed": false,
          "changes": {
            "added": ["python/async-patterns.mdc"],
            "modified": ["general/code-style.mdc"],
            "deleted": []
          },
          "reindex_triggered": true,
          "last_sync": "2026-01-13T10:30:00Z"
        }

        Example 2: Push local changes to remote
        >>> await sync_synapse(pull=False, push=True)
        {
          "status": "success",
          "pulled": false,
          "pushed": true,
          "changes": {
            "added": [],
            "modified": ["python/type-hints.mdc"],
            "deleted": []
          },
          "reindex_triggered": false,
          "last_sync": "2026-01-13T10:35:00Z"
        }

        Example 3: Error - Synapse not initialized
        >>> await sync_synapse()
        {
          "status": "error",
          "error": "Synapse not initialized. Run setup_synapse first."
        }
    """
    try:
        project_root = get_project_root()
        managers = await get_managers(project_root)

        if "synapse" not in managers:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Synapse not initialized. Run setup_synapse first.",
                },
                indent=2,
            )

        synapse_manager = await get_manager(managers, "synapse", SynapseManager)

        # Sync Synapse
        result = await synapse_manager.sync_synapse(pull=pull, push=push)

        # Trigger reindex if there were changes
        if result.get("reindex_triggered") and "rules_manager" in managers:
            rules_manager = await get_manager(managers, "rules_manager", RulesManager)
            _ = await rules_manager.index_rules(force=True)

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def update_synapse_rule(
    category: str, file: str, content: str, commit_message: str
) -> str:
    """
    Update a Synapse rule file and push changes to all projects.

    This tool modifies a rule file in the Synapse repository, commits the
    changes with a descriptive message, and pushes to the remote repository.
    This makes the updated rule immediately available to all other projects
    using the same Synapse repository.

    Args:
        category: Category name identifying the rule type.
                  Examples: "python", "general", "markdown", "security"

        file: Rule filename within the category.
              Example: "style-guide.mdc", "async-patterns.mdc"

        content: Complete new content for the rule file.
                 Overwrites existing file content entirely.

        commit_message: Git commit message describing the change.
                       Should be descriptive and follow team conventions.

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - category: Category name (only on success)
        - file: Rule filename (only on success)
        - message: Commit message used (only on success)
        - commit_hash: Git commit hash (optional, if available)
        - error: Error message (only present if status is "error")

    Examples:
        Example 1: Update a Python style guide rule
        >>> await update_synapse_rule(
        ...     category="python",
        ...     file="style-guide.mdc",
        ...     content="# Python Style Guide\n\n## Type Hints\n\nAll functions must...",
        ...     commit_message="Update Python style guide with type hint requirements"
        ... )
        {
          "status": "success",
          "category": "python",
          "file": "style-guide.mdc",
          "message": "Update Python style guide with type hint requirements",
          "commit_hash": "a1b2c3d4e5f6"
        }

        Example 2: Error - Synapse not initialized
        >>> await update_synapse_rule(
        ...     category="python",
        ...     file="test.mdc",
        ...     content="test",
        ...     commit_message="test"
        ... )
        {
          "status": "error",
          "error": "Synapse not initialized. Run setup_synapse first."
        }
    """
    try:
        project_root = get_project_root()
        managers = await get_managers(project_root)

        if "synapse" not in managers:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Synapse not initialized. Run setup_synapse first.",
                },
                indent=2,
            )

        synapse_manager = await get_manager(managers, "synapse", SynapseManager)

        # Update Synapse rule
        result = await synapse_manager.update_synapse_rule(
            category=category, file=file, content=content, commit_message=commit_message
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def get_synapse_rules(
    task_description: str,
    max_tokens: int = 10000,
    min_relevance_score: float = 0.3,
    project_files: str | None = None,
    rule_priority: str = "local_overrides_shared",
    context_aware: bool = True,
) -> str:
    """
    Get intelligently selected rules based on task context and project characteristics.

    This tool analyzes your task description and project files to automatically
    select the most relevant coding rules from both Synapse and local sources.
    It detects programming languages, frameworks, and task types to load
    appropriate rules while respecting token budget constraints.

    Args:
        task_description: Natural language description of your current task.
                         Used for keyword extraction and semantic matching.

        max_tokens: Maximum total tokens to include in response.
                   Default: 10000

        min_relevance_score: Minimum relevance score (0.0-1.0) for rule inclusion.
                            Default: 0.3

        project_files: Comma-separated list of file paths for context detection.
                      Optional - if not provided, uses task_description only.

        rule_priority: Conflict resolution strategy when Synapse and local rules overlap.
                      "local_overrides_shared": Prefer project-specific rules (default)
                      "shared_overrides_local": Prefer team-wide Synapse rules

        context_aware: Enable intelligent context detection and rule selection.
                      Default: True

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - task_description: Echo of input task description
        - context: Detected context information
        - rules_loaded: Categorized rules (generic, language, local)
        - total_tokens: Actual token count of returned rules
        - token_budget: Maximum token limit specified
        - source: Rules source ("mixed", "shared_only", "local_only")

    Examples:
        Example 1: Get rules for Python async task
        >>> await get_synapse_rules(
        ...     task_description="Implement async file operations with proper error handling",
        ...     max_tokens=8000,
        ...     min_relevance_score=0.4
        ... )
        {
          "status": "success",
          "task_description": "Implement async file operations with proper error handling",
          "context": {
            "languages": ["python"],
            "frameworks": [],
            "task_type": "implementation"
          },
          "rules_loaded": {
            "generic": [
              {
                "file": "general/error-handling.mdc",
                "tokens": 450,
                "priority": "high",
                "relevance_score": 0.92
              }
            ],
            "language": [
              {
                "file": "python/async-patterns.mdc",
                "category": "python",
                "tokens": 680,
                "priority": "high",
                "relevance_score": 0.88
              }
            ],
            "local": []
          },
          "total_tokens": 1130,
          "token_budget": 8000,
          "source": "mixed"
        }

        Example 2: Get rules with project file context
        >>> await get_synapse_rules(
        ...     task_description="Refactor authentication module",
        ...     project_files="src/auth.py, tests/test_auth.py",
        ...     max_tokens=10000
        ... )
        {
          "status": "success",
          "task_description": "Refactor authentication module",
          "context": {
            "languages": ["python"],
            "frameworks": [],
            "task_type": "refactoring"
          },
          "rules_loaded": {
            "generic": [
              {
                "file": "general/refactoring-patterns.mdc",
                "tokens": 520,
                "priority": "medium",
                "relevance_score": 0.75
              }
            ],
            "language": [
              {
                "file": "python/code-organization.mdc",
                "category": "python",
                "tokens": 420,
                "priority": "medium",
                "relevance_score": 0.68
              }
            ],
            "local": []
          },
          "total_tokens": 940,
          "token_budget": 10000,
          "source": "mixed"
        }
    """
    try:
        result = await _execute_rules_with_context(
            task_description,
            max_tokens,
            min_relevance_score,
            project_files,
            rule_priority,
            context_aware,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


def _build_category_prompts_response(
    category: str, prompts: list[dict[str, object]]
) -> str:
    """Build JSON response for category-specific prompts."""
    return json.dumps(
        {
            "status": "success",
            "category": category,
            "prompts": format_prompts_list(prompts),
            "total_count": len(prompts),
        },
        indent=2,
    )


def _build_all_prompts_response(
    prompts: list[dict[str, object]], categories: list[str]
) -> str:
    """Build JSON response for all prompts."""
    return json.dumps(
        {
            "status": "success",
            "categories": categories,
            "prompts": format_prompts_list(prompts),
            "total_count": len(prompts),
        },
        indent=2,
    )


@mcp.tool()
async def get_synapse_prompts(category: str | None = None) -> str:
    """
    Get prompts from Synapse repository.

    This tool retrieves prompts from the Synapse repository, optionally
    filtered by category. Prompts are shared across projects and can be
    used for common tasks, templates, or workflows.

    Args:
        category: Optional category name to filter prompts.
                  Examples: "python", "general", "testing"
                  If not provided, returns all prompts from all categories.

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - prompts: List of prompt objects with file, name, description, keywords
        - categories: List of available categories (if no category specified)
        - total_count: Number of prompts returned
        - error: Error message (only present if status is "error")

    Examples:
        Example 1: Get all prompts
        >>> await get_synapse_prompts()
        {
          "status": "success",
          "categories": ["python", "general", "testing"],
          "prompts": [
            {
              "file": "code-review.md",
              "name": "Code Review",
              "category": "general",
              "description": "Comprehensive code review checklist",
              "keywords": ["review", "quality", "checklist"]
            },
            {
              "file": "refactor-template.md",
              "name": "Refactoring Template",
              "category": "python",
              "description": "Template for refactoring Python code",
              "keywords": ["refactor", "python", "template"]
            }
          ],
          "total_count": 2
        }

        Example 2: Get prompts for specific category
        >>> await get_synapse_prompts(category="python")
        {
          "status": "success",
          "category": "python",
          "prompts": [
            {
              "file": "refactor-template.md",
              "name": "Refactoring Template",
              "category": "python",
              "description": "Template for refactoring Python code",
              "keywords": ["refactor", "python", "template"]
            }
          ],
          "total_count": 1
        }

        Example 3: Error - Synapse not initialized
        >>> await get_synapse_prompts()
        {
          "status": "error",
          "error": "Synapse not initialized. Run setup_synapse first."
        }
    """
    try:
        project_root = get_project_root()
        managers = await get_managers(project_root)

        if "synapse" not in managers:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Synapse not initialized. Run setup_synapse first.",
                },
                indent=2,
            )

        synapse_manager = await get_manager(managers, "synapse", SynapseManager)
        _ = await synapse_manager.load_prompts_manifest()

        if category:
            prompts = await synapse_manager.load_prompts_category(category)
            return _build_category_prompts_response(category, prompts)
        else:
            prompts = await synapse_manager.get_all_prompts()
            categories = synapse_manager.get_prompt_categories()
            return _build_all_prompts_response(prompts, categories)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def update_synapse_prompt(
    category: str, file: str, content: str, commit_message: str
) -> str:
    """
    Update a Synapse prompt file and push changes to all projects.

    This tool modifies a prompt file in the Synapse repository, commits the
    changes with a descriptive message, and pushes to the remote repository.
    This makes the updated prompt immediately available to all other projects
    using the same Synapse repository.

    Args:
        category: Category name identifying the prompt type.
                  Examples: "python", "general", "testing"

        file: Prompt filename within the category.
              Example: "code-review.md", "refactor-template.md"

        content: Complete new content for the prompt file.
                 Overwrites existing file content entirely.

        commit_message: Git commit message describing the change.
                       Should be descriptive and follow team conventions.

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - category: Category name (only on success)
        - file: Prompt filename (only on success)
        - message: Commit message used (only on success)
        - type: "prompt" (only on success)
        - commit_hash: Git commit hash (optional, if available)
        - error: Error message (only present if status is "error")

    Examples:
        Example 1: Update a code review prompt
        >>> await update_synapse_prompt(
        ...     category="general",
        ...     file="code-review.md",
        ...     content="# Code Review Checklist\n\n## Security\n\n- Check for...",
        ...     commit_message="Add security section to code review prompt"
        ... )
        {
          "status": "success",
          "category": "general",
          "file": "code-review.md",
          "message": "Add security section to code review prompt",
          "type": "prompt",
          "commit_hash": "b2c3d4e5f6a7"
        }

        Example 2: Error - Synapse not initialized
        >>> await update_synapse_prompt(
        ...     category="general",
        ...     file="test.md",
        ...     content="test",
        ...     commit_message="test"
        ... )
        {
          "status": "error",
          "error": "Synapse not initialized. Run setup_synapse first."
        }
    """
    try:
        project_root = get_project_root()
        managers = await get_managers(project_root)

        if "synapse" not in managers:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Synapse not initialized. Run setup_synapse first.",
                },
                indent=2,
            )

        synapse_manager = await get_manager(managers, "synapse", SynapseManager)

        # Update Synapse prompt
        result = await synapse_manager.update_synapse_prompt(
            category=category, file=file, content=content, commit_message=commit_message
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


# ============================================================================
# Helper Functions
# ============================================================================


async def _execute_rules_with_context(
    task_description: str,
    max_tokens: int,
    min_relevance_score: float,
    project_files: str | None,
    rule_priority: str,
    context_aware: bool,
) -> dict[str, object]:
    """Execute rules with context workflow.

    Args:
        task_description: Description of task
        max_tokens: Maximum tokens
        min_relevance_score: Minimum relevance score
        project_files: Optional project files string
        rule_priority: Rule priority setting
        context_aware: Whether context aware

    Returns:
        Result dictionary (success or error)
    """
    project_root = get_project_root()
    managers = await get_managers(project_root)

    validation_error = validate_rules_manager(managers)
    if validation_error:
        return validation_error

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


def validate_rules_manager(managers: dict[str, object]) -> dict[str, object] | None:
    """Validate rules manager exists.

    Args:
        managers: Managers dictionary

    Returns:
        Error dict if validation fails, None otherwise
    """
    if "rules_manager" not in managers:
        return {
            "status": "error",
            "error": "Rules manager not initialized. Enable rules in configuration first.",
        }
    return None


def parse_project_files(project_files: str | None) -> list[Path] | None:
    """Parse project files string into list of paths.

    Args:
        project_files: Comma-separated file paths string

    Returns:
        List of Path objects or None
    """
    if not project_files:
        return None
    return [Path(f.strip()) for f in project_files.split(",") if f.strip()]


def format_rules_response(
    result: dict[str, object], task_description: str, max_tokens: int
) -> dict[str, object]:
    """Format rules response dictionary.

    Args:
        result: Rules result dictionary
        task_description: Task description
        max_tokens: Maximum tokens

    Returns:
        Formatted response dict
    """
    return {
        "status": "success",
        "task_description": task_description,
        "context": result.get("context", {}),
        "rules_loaded": {
            "generic": extract_and_format_rules(result, "generic_rules"),
            "language": format_language_rules_list(
                extract_rules_list(result, "language_rules")
            ),
            "local": extract_and_format_rules(result, "local_rules"),
        },
        "total_tokens": result.get("total_tokens", 0),
        "token_budget": max_tokens,
        "source": result.get("source", "local_only"),
    }


def extract_rules_list(result: dict[str, object], key: str) -> list[object]:
    """Extract rules list from result dictionary.

    Args:
        result: Result dictionary
        key: Key for rules list

    Returns:
        Rules list
    """
    rules_raw = result.get(key, [])
    if isinstance(rules_raw, list):
        return cast(list[object], rules_raw)
    return []


def extract_and_format_rules(
    result: dict[str, object], key: str
) -> list[dict[str, object]]:
    """Extract and format rules list.

    Args:
        result: Result dictionary
        key: Key for rules list

    Returns:
        Formatted rules list
    """
    rules_list = extract_rules_list(result, key)
    return format_rules_list(rules_list)
