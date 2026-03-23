"""Sync Synapse cursor-agent definitions into .cursor/ and .claude/ trees."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.path_resolver import (
    CortexResourceType,
    CursorResourceType,
    get_cortex_path,
    get_cursor_path,
)
from cortex.tools.synapse.prompts_content import (
    CLAUDE_CODE_TOOLS_FIELD,
    CORTEX_TOOL_NAMES,
    MCP_TOOL_PREFIX,
)


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
    project_root = source.parent.parent.parent
    return get_cursor_path(project_root, CursorResourceType.CURSOR_DIR) / "agents"


def get_claude_agents_target(source: Path) -> Path:
    """Resolve .claude/agents/ from project root inferred via source path."""
    # source is <project_root>/.cortex/synapse/cursor-agents
    return source.parent.parent.parent / ".claude" / "agents"


def rewrite_tool_refs(body: str) -> str:
    """Replace bare `tool_name(` references with `mcp__cortex__tool_name(` in body text.

    Only rewrites occurrences that are already prefixed with a backtick (i.e. inside
    inline code spans like `tool_name(`), to avoid false-positive rewrites in prose.
    """

    def replacer(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in CORTEX_TOOL_NAMES:
            return f"`{MCP_TOOL_PREFIX}{name}("
        return m.group(0)

    return re.sub(r"`(\w+)\(", replacer, body)


def inject_tools_into_frontmatter(content: str) -> str:
    """Transform agent content for Claude Code: inject tools field and rewrite tool refs.

    Two changes are applied to the Claude Code copy of each agent file:
    1. `tools: mcp__cortex__*` is added to YAML frontmatter so Claude Code
       grants the agent permission to call all Cortex MCP tools.
    2. Bare backtick tool references like `health_check(` are
       rewritten to `mcp__cortex__health_check(` so the LLM
       unambiguously invokes the right tool without any name-to-prefix mapping.

    Cursor agents do not use these fields (frontmatter `tools:` is ignored,
    plain names work natively), so the source files stay clean.

    If no frontmatter is present, only the tool-ref rewrite is applied.
    """
    if not content.startswith("---"):
        return rewrite_tool_refs(content)
    end = content.find("\n---", 3)
    if end == -1:
        return rewrite_tool_refs(content)
    frontmatter = content[3:end]
    closing = end + 4  # position just after "\n---"
    body = content[closing:]

    if "tools:" not in frontmatter:
        injected_fm = (
            content[:end] + f"\n{CLAUDE_CODE_TOOLS_FIELD}" + content[end:closing]
        )
    else:
        injected_fm = content[:closing]

    return injected_fm + rewrite_tool_refs(body)


def sync_agent_file(agent_file: Path, target: Path, transform: bool = False) -> bool:
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


def sync_agents_to_target(
    source: Path, target: Path, label: str, transform: bool = False
) -> int:
    """Sync all .md agent files from source to target. Returns count written.

    Also removes stale .md files in target that no longer exist in source.
    """
    from cortex.core.logging_config import logger

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"sync_cursor_agents: could not create {target}: {e}")
        return 0

    source_names = {f.name for f in source.glob("*.md")}
    synced = sum(
        sync_agent_file(f, target, transform=transform)
        for f in sorted(source.glob("*.md"))
    )
    # Remove stale agent files that no longer exist in source
    for stale in sorted(target.glob("*.md")):
        if stale.name not in source_names:
            try:
                stale.unlink()
                logger.info(f"Removed stale agent {stale.name} from {target}")
            except OSError:
                pass
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

    _ = sync_agents_to_target(source, get_cursor_agents_target(source), "cursor")
    _ = sync_agents_to_target(
        source, get_claude_agents_target(source), "claude-code", transform=True
    )
