"""Constants for Synapse prompt registration and Claude Code agent transforms."""

SYNAPSE_PROMPT_ICONS: dict[str, str] = {
    "commit": "💾",
    "review": "👀",
    "implement": "⚡",
    "plan": "📋",
    "analyze": "🔍",
}
DEFAULT_PROMPT_ICON = "📝"

CLAUDE_CODE_TOOLS_FIELD = "tools: mcp__cortex__*"

# All Cortex MCP tool names — used to rewrite bare `tool(` references in
# agent instructions so Claude Code can call them as `mcp__cortex__tool(`.
CORTEX_TOOL_NAMES: frozenset[str] = frozenset(
    [
        "autofix",
        "manage_file",
        "pipeline_handoff",
        "plan",
        "run_docs_gate",
        "run_quality_gate",
        "session",
        "think",
        "update_memory_bank",
        "write_artifact",
    ]
)

MCP_TOOL_PREFIX = "mcp__cortex__"
