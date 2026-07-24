"""Task type inference for scoped context/rules assembly."""

from __future__ import annotations

from cortex.core.models import TaskType

_PLAN_TEXT_HINTS: tuple[tuple[TaskType, tuple[str, ...]], ...] = (
    (TaskType.TEST, ("test", "pytest", "coverage", "assert")),
    (TaskType.MCP_TOOL, ("mcp tool", "tool handler", "@mcp.tool", "tool")),
    (
        TaskType.MCP_RESOURCE,
        ("mcp resource", "@mcp.resource", "resource uri", "cortex://"),
    ),
    (TaskType.PROMPT, ("prompt", "claude-agent", "synapse", "agent prompt")),
    (TaskType.SCHEMA, ("pydantic", "schema", "basemodel", "model")),
    (TaskType.INFRA, ("ci", "workflow", "pipeline", "makefile", "build")),
    (TaskType.DOCUMENTATION, ("readme", "markdown", "docs", "docstring")),
    (
        TaskType.CORE_LOGIC,
        ("python", "typescript", "javascript", "refactor", "core", "utility", "logic"),
    ),
)


_CORE_LOGIC_EXTENSIONS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".swift",
    ".kt",
    ".java",
    ".rb",
    ".cs",
)


def _match_direct_file_signals(lower_path: str) -> set[TaskType]:
    matches: set[TaskType] = set()
    if "test" in lower_path or lower_path.startswith("tests/"):
        matches.add(TaskType.TEST)
    if "/tools/" in lower_path:
        matches.add(TaskType.MCP_TOOL)
    if "/resources/" in lower_path:
        matches.add(TaskType.MCP_RESOURCE)
    if lower_path.endswith(".md") or "/docs/" in lower_path:
        matches.add(TaskType.DOCUMENTATION)
    if "/synapse/" in lower_path or "prompt" in lower_path:
        matches.add(TaskType.PROMPT)
    if "schema" in lower_path or "model" in lower_path:
        matches.add(TaskType.SCHEMA)
    return matches


def _match_extension_signals(lower_path: str) -> set[TaskType]:
    matches: set[TaskType] = set()
    if lower_path.endswith(_CORE_LOGIC_EXTENSIONS):
        matches.add(TaskType.CORE_LOGIC)
    if lower_path.endswith((".yml", ".yaml", ".toml")):
        matches.add(TaskType.INFRA)
    return matches


def _classify_file_path(file_path: str) -> set[TaskType]:
    lower_path = file_path.lower()
    matches = _match_direct_file_signals(lower_path)
    matches.update(_match_extension_signals(lower_path))
    return matches


def infer_task_type(plan_content: str, files_touched: list[str]) -> list[TaskType]:
    """Infer one or more TaskType values from plan text and touched files."""
    inferred: set[TaskType] = set()
    content = plan_content.lower()
    for task_type, hints in _PLAN_TEXT_HINTS:
        if any(hint in content for hint in hints):
            inferred.add(task_type)
    for file_path in files_touched:
        inferred.update(_classify_file_path(file_path))
    if not inferred:
        return [TaskType.ALL]
    return sorted(inferred, key=lambda item: item.value)
