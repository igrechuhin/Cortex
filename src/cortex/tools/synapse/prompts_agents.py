"""Sync Synapse subagent definitions into the .claude/ tree."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.synapse.prompts_content import (
    CLAUDE_CODE_TOOLS_FIELD,
    CORTEX_TOOL_NAMES,
    MCP_TOOL_PREFIX,
)


def get_agents_source(project_root: Path | None = None) -> Path | None:
    """Find .cortex/synapse/claude-agents/.

    When *project_root* is provided the lookup is scoped to that directory.
    When ``None``, falls back to walking up from CWD then from the module file
    location (backward-compatible heuristic for dev installs).
    """
    if project_root is not None:
        candidate = (
            get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
            / "synapse"
            / "claude-agents"
        )
        return candidate if (candidate.exists() and candidate.is_dir()) else None

    current = Path.cwd()
    for path in [current, *current.parents]:
        candidate = (
            get_cortex_path(path, CortexResourceType.CORTEX_DIR)
            / "synapse"
            / "claude-agents"
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
            / "claude-agents"
        )
        if candidate.exists() and candidate.is_dir():
            return candidate

    return None


def get_claude_agents_target(source: Path) -> Path:
    """Resolve .claude/agents/ from project root inferred via source path."""
    # source is <project_root>/.cortex/synapse/claude-agents
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

    The Synapse source files stay clean of these fields; they are injected
    only into the Claude Code copy.

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
        logger.warning(f"sync_claude_agents: could not write {dest}: {e}")
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
        logger.warning(f"sync_claude_agents: could not create {target}: {e}")
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


def sync_claude_agents(project_root: Path | None = None) -> None:
    """Sync Synapse subagents to .claude/agents/.

    Copies all .md files from .cortex/synapse/claude-agents/ to the Claude Code
    agent directory so the commit and implement pipelines have their
    subagents available.

    When *project_root* is provided the lookup is scoped to that directory.
    When ``None``, falls back to the CWD/module-anchor heuristic.

    Idempotent: files are only written when content changes. Creates target
    directories if absent.
    """
    source = get_agents_source(project_root)
    if not source:
        return

    _ = sync_agents_to_target(
        source, get_claude_agents_target(source), "claude-code", transform=True
    )
