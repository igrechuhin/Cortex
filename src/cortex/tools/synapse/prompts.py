"""
Dynamic Prompts Registration

This module loads prompts from two locations and registers them as MCP prompts:
1. .cortex/synapse/prompts/ - Shared prompts from Synapse (language-agnostic)
2. .cortex/prompts/ - Project-specific prompts (e.g., Cortex MCP tools)

Prompts are loaded synchronously at import time to enable decorator registration.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.icon_helpers import create_emoji_icon
from cortex.core.models import JsonDict, JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.server import mcp

SYNAPSE_PROMPT_ICONS: dict[str, str] = {
    "commit": "💾",
    "review": "👀",
    "implement": "⚡",
    "plan": "📋",
    "analyze": "🔍",
}
DEFAULT_PROMPT_ICON = "📝"

# Explicitly reference mcp to satisfy type checker (module imported for registration side effects)
_ = mcp


def get_prompts_paths() -> list[Path]:
    """Get paths to all prompts directories.

    Walks up the directory tree from current working directory to find
    prompts directories. Returns paths for both:
    - .cortex/synapse/prompts/ (shared Synapse prompts)
    - .cortex/prompts/ (project-specific prompts)

    Also tries to find them relative to the module file location as fallback.
    """
    found_paths: list[Path] = []

    # Directories to check (relative to .cortex/)
    prompt_dirs = ["synapse/prompts", "prompts"]

    # Try current working directory first (works when server runs from project root)
    current = Path.cwd()
    for path in [current, *current.parents]:
        cortex_root = get_cortex_path(path, CortexResourceType.CORTEX_DIR)
        for prompt_dir in prompt_dirs:
            prompts_path = cortex_root / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                if prompts_path not in found_paths:
                    found_paths.append(prompts_path)

    # Fallback: try relative to this module's location
    # This helps when CWD is not the project root
    module_file = Path(__file__)
    # Go up from src/cortex/tools/synapse/prompts.py to project root
    for path in [
        module_file.parent.parent.parent.parent,
        *module_file.parent.parent.parent.parent.parents,
    ]:
        cortex_root = get_cortex_path(path, CortexResourceType.CORTEX_DIR)
        for prompt_dir in prompt_dirs:
            prompts_path = cortex_root / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                if prompts_path not in found_paths:
                    found_paths.append(prompts_path)

    return found_paths


def get_synapse_prompts_path() -> Path | None:
    """Get path to Synapse prompts directory (for backwards compatibility)."""
    paths = get_prompts_paths()
    for path in paths:
        if "synapse" in str(path):
            return path
    return paths[0] if paths else None


def load_prompts_manifest(prompts_path: Path) -> JsonDict | None:
    """Load prompts manifest synchronously."""
    manifest_path = prompts_path / "prompts-manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
            return JsonDict.from_dict(data)
    except Exception:
        return None


def load_prompt_content(prompts_path: Path, category: str, filename: str) -> str | None:
    """Load prompt file content synchronously."""
    # Prompts are in the root of prompts/ directory, not in category subdirectories
    # Apply path traversal protection to ensure files stay within prompts_path.
    base_dir = prompts_path.resolve()

    candidate = prompts_path / filename

    # Reject absolute paths or explicit parent directory traversal segments
    filename_path = Path(filename)
    if filename_path.is_absolute() or ".." in filename_path.parts:
        return None

    try:
        resolved = candidate.resolve()
    except OSError:
        return None

    # Ensure the resolved path is within the prompts base directory
    try:
        _ = resolved.relative_to(base_dir)
    except ValueError:
        return None

    if not resolved.exists() or not resolved.is_file():
        return None

    try:
        with open(resolved, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _emoji_for_prompt(func_name: str) -> str:
    """Return emoji for a prompt by name; fallback to default."""
    return SYNAPSE_PROMPT_ICONS.get(func_name, DEFAULT_PROMPT_ICON)


def create_prompt_function(
    name: str,
    content: str,
    description: str,
    icon_emoji: str | None = None,
) -> None:
    """Create and register a prompt function dynamically.

    Stores content in a module-level dict and creates a function that references it.
    """
    # Store content in module-level dict to avoid closure issues
    if "_prompt_contents" not in globals():
        globals()["_prompt_contents"] = {}
    globals()["_prompt_contents"][name] = content

    emoji = icon_emoji if icon_emoji else _emoji_for_prompt(name)
    icon = create_emoji_icon(emoji)

    def prompt_func() -> str:
        """Return prompt content."""
        return globals()["_prompt_contents"][name]

    # Preserve the generated function's name and description for introspection
    prompt_func.__name__ = name
    prompt_func.__doc__ = description

    decorated = mcp.prompt(icons=[icon])(prompt_func)
    globals()[name] = decorated


def process_prompt_info(
    prompt_info: ModelDict, prompts_path: Path, category_name: str
) -> int:
    """Process a single prompt info and register it.

    Returns:
        Number of prompts registered (0 or 1)
    """
    filename = prompt_info.get("file")
    if not isinstance(filename, str):
        return 0

    prompt_name = prompt_info.get("name", filename.replace(".md", "").replace("-", "_"))
    if not isinstance(prompt_name, str):
        return 0

    description = prompt_info.get("description", "")
    if not isinstance(description, str):
        description = ""

    icon_emoji: str | None = None
    icon_raw = prompt_info.get("icon")
    if isinstance(icon_raw, str):
        icon_emoji = icon_raw

    content = load_prompt_content(prompts_path, category_name, filename)
    if not content:
        return 0

    func_name = prompt_name.lower().replace(" ", "_").replace("-", "_")
    func_name = "".join(c if c.isalnum() or c == "_" else "_" for c in func_name)

    try:
        create_prompt_function(func_name, content, description, icon_emoji=icon_emoji)
        return 1
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning(f"Failed to register prompt {func_name}: {e}")
        return 0


def log_registration_summary(registered_count: int) -> None:
    """Log registration summary and verify functions exist."""
    if registered_count > 0:
        from cortex.core.logging_config import logger

        logger.info(f"Registered {registered_count} Synapse prompts")
        registered_names = [
            name
            for name in globals()
            if name.startswith("commit_")
            or name.startswith("fix_")
            or name.startswith("review_")
            or name.startswith("run_")
        ]
        logger.debug(f"Registered prompt functions in namespace: {registered_names}")


def register_prompts_from_path(prompts_path: Path) -> int:
    """Load and register prompts from a single path.

    Returns:
        Number of prompts registered from this path.
    """
    manifest = load_prompts_manifest(prompts_path)
    if not manifest:
        return 0

    manifest_dict = cast(ModelDict, manifest.model_dump(mode="json"))
    categories = manifest_dict.get("categories")
    if not isinstance(categories, dict):
        return 0

    registered_count = 0
    for category_name, category_info in cast(ModelDict, categories).items():
        if not isinstance(category_info, dict):
            continue

        prompts_list_raw: JsonValue = cast(ModelDict, category_info).get("prompts", [])
        if not isinstance(prompts_list_raw, list):
            continue

        for prompt_info_raw in cast(list[JsonValue], prompts_list_raw):
            if isinstance(prompt_info_raw, dict):
                prompt_info = cast(ModelDict, prompt_info_raw)
                registered_count += process_prompt_info(
                    prompt_info, prompts_path, category_name
                )

    return registered_count


def register_synapse_prompts() -> None:
    """Load and register all prompts from Synapse and project-specific directories."""
    prompts_paths = get_prompts_paths()
    if not prompts_paths:
        return

    total_registered = 0
    for prompts_path in prompts_paths:
        registered = register_prompts_from_path(prompts_path)
        total_registered += registered

    log_registration_summary(total_registered)


def get_cursor_agents_source() -> Path | None:
    """Find .cortex/synapse/cursor-agents/ by walking up from CWD and module location."""
    current = Path.cwd()
    for path in [current, *current.parents]:
        candidate = (
            get_cortex_path(path, CortexResourceType.CORTEX_DIR)
            / "synapse"
            / "cursor-agents"
        )
        if candidate.exists() and candidate.is_dir():
            return candidate

    module_file = Path(__file__)
    for path in [
        module_file.parent.parent.parent.parent,
        *module_file.parent.parent.parent.parent.parents,
    ]:
        candidate = (
            get_cortex_path(path, CortexResourceType.CORTEX_DIR)
            / "synapse"
            / "cursor-agents"
        )
        if candidate.exists() and candidate.is_dir():
            return candidate

    return None


def get_cursor_agents_target(source: Path) -> Path:
    """Resolve .cursor/agents/ from project root inferred via source path."""
    # source is <project_root>/.cortex/synapse/cursor-agents
    from cortex.core.path_resolver import CursorResourceType, get_cursor_path

    project_root = source.parent.parent.parent
    return get_cursor_path(project_root, CursorResourceType.CURSOR_DIR) / "agents"


def get_claude_agents_target(source: Path) -> Path:
    """Resolve .claude/agents/ from project root inferred via source path."""
    # source is <project_root>/.cortex/synapse/cursor-agents
    return source.parent.parent.parent / ".claude" / "agents"


CLAUDE_CODE_TOOLS_FIELD = "tools: mcp__cortex__*"

# All Cortex MCP tool names — used to rewrite bare `tool(` references in
# agent instructions so Claude Code can call them as `mcp__cortex__tool(`.
_CORTEX_TOOL_NAMES: frozenset[str] = frozenset(
    [
        "analyze",
        "analyze_error_patterns",
        "apply_refactoring",
        "check_mcp_connection_health",
        "check_structure_health",
        "configure",
        "execute_pre_commit_checks",
        "fix_markdown_lint",
        "fix_quality_issues",
        "get_last_pre_commit_status",
        "get_pre_commit_job_status",
        "get_relevance_scores",
        "get_structure_info",
        "load_context",
        "manage_file",
        "manage_session_scripts",
        "pipeline_handoff",
        "plan",
        "query_memory_bank",
        "query_usage",
        "roadmap",
        "rules",
        "run_composite_workflow",
        "run_tool_evaluation",
        "search_tools",
        "session",
        "start_pre_commit_job",
        "suggest_refactoring",
        "summarize_content",
        "synapse",
        "think",
        "update_memory_bank",
        "validate",
    ]
)

_MCP_PREFIX = "mcp__cortex__"


def _rewrite_tool_refs(body: str) -> str:
    """Replace bare `tool_name(` references with `mcp__cortex__tool_name(` in body text.

    Only rewrites occurrences that are already prefixed with a backtick (i.e. inside
    inline code spans like `tool_name(`), to avoid false-positive rewrites in prose.
    """
    import re

    def replacer(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in _CORTEX_TOOL_NAMES:
            return f"`{_MCP_PREFIX}{name}("
        return m.group(0)

    return re.sub(r"`(\w+)\(", replacer, body)


def inject_tools_into_frontmatter(content: str) -> str:
    """Transform agent content for Claude Code: inject tools field and rewrite tool refs.

    Two changes are applied to the Claude Code copy of each agent file:
    1. `tools: mcp__cortex__*` is added to YAML frontmatter so Claude Code
       grants the agent permission to call all Cortex MCP tools.
    2. Bare backtick tool references like `check_mcp_connection_health(` are
       rewritten to `mcp__cortex__check_mcp_connection_health(` so the LLM
       unambiguously invokes the right tool without any name-to-prefix mapping.

    Cursor agents do not use these fields (frontmatter `tools:` is ignored,
    plain names work natively), so the source files stay clean.

    If no frontmatter is present, only the tool-ref rewrite is applied.
    """
    if not content.startswith("---"):
        return _rewrite_tool_refs(content)
    end = content.find("\n---", 3)
    if end == -1:
        return _rewrite_tool_refs(content)
    frontmatter = content[3:end]
    closing = end + 4  # position just after "\n---"
    body = content[closing:]

    if "tools:" not in frontmatter:
        injected_fm = (
            content[:end] + f"\n{CLAUDE_CODE_TOOLS_FIELD}" + content[end:closing]
        )
    else:
        injected_fm = content[:closing]

    return injected_fm + _rewrite_tool_refs(body)


def _sync_agent_file(agent_file: Path, target: Path, transform: bool = False) -> bool:
    """Write agent file to target if content differs. Returns True if written."""
    from cortex.core.logging_config import logger

    content = agent_file.read_text(encoding="utf-8")
    if transform:
        content = inject_tools_into_frontmatter(content)
    dest = target / agent_file.name
    if dest.exists() and dest.read_text(encoding="utf-8") == content:
        return False
    try:
        _ = dest.write_text(content, encoding="utf-8")
        return True
    except OSError as e:
        logger.warning(f"sync_cursor_agents: could not write {dest}: {e}")
        return False


def _sync_agents_to_target(
    source: Path, target: Path, label: str, transform: bool = False
) -> int:
    """Sync all .md agent files from source to target. Returns count written."""
    from cortex.core.logging_config import logger

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"sync_cursor_agents: could not create {target}: {e}")
        return 0

    synced = sum(
        _sync_agent_file(f, target, transform=transform)
        for f in sorted(source.glob("*.md"))
    )
    if synced > 0:
        logger.info(f"Synced {synced} agent(s) to {target} ({label})")
    return synced


def sync_cursor_agents() -> None:
    """Sync cursor agents to .cursor/agents/ and .claude/agents/.

    Copies all .md files from .cortex/synapse/cursor-agents/ to both IDE
    agent directories so the commit and implement pipelines work in both
    Cursor (primary) and Claude Code (secondary).

    Idempotent: files are only written when content changes. Creates target
    directories if absent. Called at import time so agents are always in sync
    when the MCP server starts.
    """
    source = get_cursor_agents_source()
    if not source:
        return

    _ = _sync_agents_to_target(source, get_cursor_agents_target(source), "cursor")
    _ = _sync_agents_to_target(
        source, get_claude_agents_target(source), "claude-code", transform=True
    )


# Register prompts and sync cursor agents at import time
register_synapse_prompts()
sync_cursor_agents()
