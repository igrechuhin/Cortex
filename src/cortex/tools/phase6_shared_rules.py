"""
Phase 6: Shared Rules Repository Tools

This module contains tools for syncing, updating, and retrieving
shared rules from a git submodule-based repository.

Total: 3 tools
- sync_shared_rules
- update_shared_rule
- get_rules_with_context

Note: setup_shared_rules has been replaced by a prompt template in docs/prompts/
"""

import json
from pathlib import Path
from typing import cast

from cortex.managers.initialization import get_managers, get_project_root
from cortex.optimization.rules_manager import RulesManager
from cortex.rules.shared_rules_manager import SharedRulesManager
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


@mcp.tool()
async def sync_shared_rules(pull: bool = True, push: bool = False) -> str:
    """
    Sync shared rules repository with remote using git operations.

    This tool synchronizes the local shared rules git submodule with the remote
    repository. When pulling, it fetches the latest rules from other projects
    that share the same rules repository. When pushing, it shares local rule
    modifications with all other projects. After pulling changes, the rules
    index is automatically rebuilt to incorporate new or modified rules.

    The shared rules repository is typically a git submodule in .shared-rules/
    that contains language-specific and generic coding rules organized by
    category (e.g., python/, javascript/, generic/).

    Args:
        pull: Pull latest changes from remote repository.
              Set to True to fetch rule updates from other projects.
              Triggers automatic rules reindexing if changes are detected.
              Default: True
              Example: pull=True retrieves updated security guidelines

        push: Push local changes to remote repository.
              Set to True to share your local rule modifications with other projects.
              Requires commit access to the shared rules repository.
              Default: False
              Example: push=True shares your updated Python style guide

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - pulled: Boolean indicating if pull was performed
        - pushed: Boolean indicating if push was performed
        - changes: Dictionary with lists of added/modified/deleted files
        - reindex_triggered: Boolean indicating if rules reindex occurred
        - last_sync: ISO timestamp of sync operation
        - error: Error message (only present if status is "error")
        - error_type: Exception type name (only present if status is "error")

        Success example:
        {
          "status": "success",
          "pulled": true,
          "pushed": false,
          "changes": {
            "added": ["python/async-best-practices.md"],
            "modified": ["generic/security-guidelines.md"],
            "deleted": []
          },
          "reindex_triggered": true,
          "last_sync": "2025-01-04T10:30:45.123456"
        }

        Error example:
        {
          "status": "error",
          "error": "Shared rules not initialized. Run setup_shared_rules first.",
          "error_type": "ValueError"
        }

    Examples:
        1. Pull latest rule updates from shared repository:
           ```python
           result = await sync_shared_rules(pull=True)
           # Downloads new python/async-best-practices.md
           # Downloads updated generic/security-guidelines.md
           # Automatically rebuilds rules index
           ```

        2. Push local rule modifications to share with other projects:
           ```python
           result = await sync_shared_rules(pull=False, push=True)
           # Uploads your modified python/type-hints.md
           # Makes changes available to all projects using this rules repo
           ```

        3. Bidirectional sync (pull then push):
           ```python
           result = await sync_shared_rules(pull=True, push=True)
           # First pulls latest changes from remote
           # Then pushes any local modifications
           # Useful after editing shared rules locally
           ```

    Note:
        - Requires shared rules to be initialized via setup_shared_rules first
        - Pull operation triggers automatic rules reindexing if changes detected
        - Push operation requires write access to the shared rules repository
        - Changes are tracked using git diff-tree to identify added/modified/deleted files
        - Concurrent operations are safe - git handles merge conflicts
        - Use pull regularly to stay synchronized with team rule updates
    """
    try:
        project_root = get_project_root()
        managers = await get_managers(project_root)

        if "shared_rules" not in managers:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Shared rules not initialized. Run setup_shared_rules first.",
                },
                indent=2,
            )

        shared_rules_manager = cast(SharedRulesManager, managers["shared_rules"])

        # Sync shared rules
        result = await shared_rules_manager.sync_shared_rules(pull=pull, push=push)

        # Trigger reindex if there were changes
        if result.get("reindex_triggered") and "rules" in managers:
            rules_manager = cast(RulesManager, managers["rules"])
            _ = await rules_manager.index_rules(force=True)

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def update_shared_rule(
    category: str, file: str, content: str, commit_message: str
) -> str:
    """
    Update a shared rule file and push changes to all projects.

    This tool modifies a rule file in the shared rules repository, commits the
    changes with a descriptive message, and pushes to the remote repository.
    This makes the updated rule immediately available to all other projects
    using the same shared rules repository. The tool handles both updating
    existing rule files and creating new ones.

    After updating, other projects can pull the changes using sync_shared_rules()
    to incorporate your rule modifications. This enables centralized management
    of coding standards, best practices, and team conventions.

    Args:
        category: Category name identifying the rule type.
                  Corresponds to subdirectory in shared rules repository.
                  Examples: "python", "javascript", "typescript", "generic", "security"
                  Must be a valid directory name without path separators.
                  Case-sensitive on Unix systems.

        file: Rule filename within the category.
              Typically a Markdown file (e.g., "style-guide.md", "async-patterns.md").
              Can include subdirectories (e.g., "testing/pytest-best-practices.md").
              Must be a valid filename without absolute paths.
              Example: "type-hints.md", "security/input-validation.md"

        content: Complete new content for the rule file.
                 Overwrites existing file content entirely.
                 Typically Markdown format with headers, code examples, and explanations.
                 Should include clear guidelines, rationale, and examples.
                 Example: "# Async Patterns\n\n## Context Managers\n\nUse async with..."

        commit_message: Git commit message describing the change.
                       Should be descriptive and follow team conventions.
                       Appears in git history for all projects using this rule.
                       Examples: "Add async context manager best practices",
                                "Fix typo in security guidelines",
                                "Update Python 3.13 type hints section"

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - category: Category name (only on success)
        - file: Rule filename (only on success)
        - message: Commit message used (only on success)
        - commit_sha: Git commit hash (optional, if available)
        - error: Error message (only present if status is "error")
        - error_type: Exception type name (only present if status is "error")
        - action: "update_shared_rule" (only present if status is "error")

        Success example:
        {
          "status": "success",
          "category": "python",
          "file": "async-patterns.md",
          "message": "Add best practice for asyncio context managers",
          "commit_sha": "a1b2c3d4"
        }

        Error example:
        {
          "status": "error",
          "error": "Shared rules not initialized",
          "error_type": "ValueError",
          "action": "update_shared_rule"
        }

    Examples:
        1. Update existing Python style guide with new section:
           ```python
           content = '''# Python Style Guide

           ## Type Hints
           Use Python 3.13+ built-in types:
           - Use list[str] instead of List[str]
           - Use dict[str, int] instead of Dict[str, int]
           - Use T | None instead of Optional[T]

           ## Async Best Practices
           Always use async context managers for resources...
           '''

           result = await update_shared_rule(
               category="python",
               file="style-guide.md",
               content=content,
               commit_message="Add Python 3.13 type hints and async guidelines"
           )
           # Updates rule for entire team
           # All projects can pull this update via sync_shared_rules()
           ```

        2. Create new security rule for input validation:
           ```python
           content = '''# Input Validation

           ## Path Traversal Protection
           Always validate file paths against base directories:

           ```python
           from pathlib import Path

           def safe_path(base: Path, user_input: str) -> Path:
               path = (base / user_input).resolve()
               if not path.is_relative_to(base):
                   raise ValueError("Path traversal detected")
               return path
           ```
           '''

           result = await update_shared_rule(
               category="security",
               file="input-validation.md",
               content=content,
               commit_message="Add path traversal protection guideline"
           )
           # Creates new rule file in security/ category
           ```

        3. Fix typo in existing generic coding standards:
           ```python
           result = await update_shared_rule(
               category="generic",
               file="coding-standards.md",
               content=corrected_content,
               commit_message="Fix typo: 'recieve' -> 'receive' in examples"
           )
           # Quick fix shared across all projects
           ```

    Note:
        - Requires shared rules to be initialized via setup_shared_rules first
        - Requires write access to the shared rules repository
        - Overwrites entire file content - always provide complete content
        - Changes are immediately committed and pushed to remote
        - Creates parent directories automatically if they don't exist
        - Use descriptive commit messages - they appear in all project histories
        - Other projects must run sync_shared_rules(pull=True) to receive updates
        - Consider announcing significant rule changes to team via communication channels
    """
    try:
        project_root = get_project_root()
        managers = await get_managers(project_root)

        if "shared_rules" not in managers:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Shared rules not initialized. Run setup_shared_rules first.",
                },
                indent=2,
            )

        shared_rules_manager = cast(SharedRulesManager, managers["shared_rules"])

        # Update shared rule
        result = await shared_rules_manager.update_shared_rule(
            category=category, file=file, content=content, commit_message=commit_message
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def get_rules_with_context(
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
    select the most relevant coding rules from both shared and local sources.
    It detects programming languages, frameworks, and task types (e.g., testing,
    authentication, refactoring) to load appropriate rules while respecting
    token budget constraints.

    The context-aware selection ensures you receive rules that are actually
    relevant to your current work, avoiding information overload while
    maintaining access to critical guidelines. Rules are scored by relevance
    and filtered by configurable thresholds.

    Args:
        task_description: Natural language description of your current task.
                         Used for keyword extraction and semantic matching.
                         More detailed descriptions yield better rule selection.
                         Examples: "Implement JWT authentication in Django REST API",
                                  "Refactor async functions to use context managers",
                                  "Write pytest tests for user registration flow"

        max_tokens: Maximum total tokens to include in response.
                   Controls how many rules are returned based on token count.
                   Higher limits include more rules but may exceed context windows.
                   Default: 10000
                   Range: 1000-50000 typical
                   Example: 15000 for comprehensive guidance, 5000 for focused rules

        min_relevance_score: Minimum relevance score (0.0-1.0) for rule inclusion.
                            Rules below this threshold are excluded.
                            Lower values include more rules with looser matching.
                            Higher values return only highly relevant rules.
                            Default: 0.3
                            Example: 0.5 for strict relevance, 0.2 for broader coverage

        project_files: Comma-separated list of file paths for context detection.
                      File extensions inform language/framework detection.
                      Relative or absolute paths accepted.
                      Optional - if not provided, uses task_description only.
                      Examples: "auth.py,views.py,models.py",
                               "src/components/Login.tsx,src/utils/api.ts"

        rule_priority: Conflict resolution strategy when shared and local rules overlap.
                      "local_overrides_shared": Prefer project-specific rules (default)
                      "shared_overrides_local": Prefer team-wide shared rules
                      Local rules typically contain project-specific conventions.
                      Example: Use local_overrides_shared to enforce project standards

        context_aware: Enable intelligent context detection and rule selection.
                      When True, analyzes task and files to detect languages/frameworks.
                      When False, loads all rules without filtering.
                      Default: True
                      Example: Set False to get all available rules regardless of context

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - task_description: Echo of input task description
        - context: Detected context information
          - languages: List of detected programming languages
          - frameworks: List of detected frameworks
          - task_type: Inferred task type (e.g., "authentication", "testing")
        - rules_loaded: Categorized rules
          - generic: List of general coding rules (all languages)
          - language: List of language-specific rules (Python, JS, etc.)
          - local: List of project-specific local rules
        - total_tokens: Actual token count of returned rules
        - token_budget: Maximum token limit specified
        - source: Rules source ("mixed", "shared_only", "local_only")
        - error: Error message (only present if status is "error")
        - error_type: Exception type name (only present if status is "error")

        Each rule in rules_loaded contains:
        - file: Rule filename
        - tokens: Token count for this rule
        - priority: Priority level ("high", "medium", "low")
        - relevance_score: Computed relevance (0.0-1.0)
        - category: Category name (language rules only)

        Success example:
        {
          "status": "success",
          "task_description": "Implement JWT authentication in Django",
          "context": {
            "languages": ["python"],
            "frameworks": ["django"],
            "task_type": "authentication"
          },
          "rules_loaded": {
            "generic": [
              {
                "file": "coding-standards.md",
                "tokens": 500,
                "priority": "high",
                "relevance_score": 0.8
              },
              {
                "file": "security-guidelines.md",
                "tokens": 750,
                "priority": "high",
                "relevance_score": 0.95
              }
            ],
            "language": [
              {
                "file": "python-style.md",
                "category": "python",
                "tokens": 300,
                "priority": "medium",
                "relevance_score": 0.9
              },
              {
                "file": "django-best-practices.md",
                "category": "python",
                "tokens": 600,
                "priority": "high",
                "relevance_score": 0.85
              }
            ],
            "local": [
              {
                "file": "project-rules.md",
                "tokens": 200,
                "priority": "high",
                "relevance_score": 1.0
              }
            ]
          },
          "total_tokens": 2350,
          "token_budget": 10000,
          "source": "mixed"
        }

        Error example:
        {
          "status": "error",
          "error": "Rules manager not initialized. Enable rules in configuration first.",
          "error_type": "ValueError"
        }

    Examples:
        1. Get rules for implementing Django authentication:
           ```python
           result = await get_rules_with_context(
               task_description="Implement JWT authentication in Django REST API",
               project_files="auth.py,views.py,models.py,serializers.py"
           )
           # Returns:
           # - Generic: security-guidelines.md, api-design.md
           # - Python: django-best-practices.md, python-security.md
           # - Local: project-auth-standards.md
           # Context detects: Python, Django, authentication, REST API
           ```

        2. Get rules for React component refactoring with strict relevance:
           ```python
           result = await get_rules_with_context(
               task_description="Refactor React hooks to use TypeScript generics",
               project_files="src/components/UserProfile.tsx,src/hooks/useAuth.ts",
               max_tokens=8000,
               min_relevance_score=0.5
           )
           # Returns only highly relevant rules:
           # - Generic: refactoring-patterns.md
           # - TypeScript: typescript-generics.md, react-typescript.md
           # Context detects: TypeScript, React, refactoring
           ```

        3. Get comprehensive rules without context filtering:
           ```python
           result = await get_rules_with_context(
               task_description="General code review",
               max_tokens=20000,
               min_relevance_score=0.0,
               context_aware=False
           )
           # Returns all available rules up to token budget
           # No filtering by language or framework
           # Useful for broad code review or exploration
           ```

    Note:
        - Requires rules manager to be initialized in configuration
        - Context detection is language/framework agnostic - supports all languages
        - Language detection uses file extensions (.py, .ts, .js, .java, etc.)
        - Framework detection uses keywords and patterns in task description
        - Token counting uses tiktoken (OpenAI's tokenizer)
        - Rules are cached and indexed for fast retrieval
        - Relevance scoring combines keyword matching and semantic similarity
        - Returns empty lists if no rules match criteria
        - Local rules (project-specific) always get relevance_score of 1.0
        - Use sync_shared_rules() to update available shared rules
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

    rules_manager = cast(RulesManager, managers["rules"])
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
    if "rules" not in managers:
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


# ============================================================================
# Legacy Tools and Resources
# ============================================================================
