"""MCP tool failure recovery: investigation plans and roadmap integration.

Provides helpers that create investigation-plan files and link them into
the project roadmap when an MCP tool failure is detected.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

logger = logging.getLogger(__name__)

_PLAN_TEMPLATE = """# Phase: Investigate {tool_name} MCP Tool Failure

**Status**: PLANNING
**Priority**: ASAP (Blocker)
**Created**: {today}
**Target Completion**: {today}

## Goal

Investigate and fix MCP tool failure that occurred during commit procedure execution.

## Context

**Problem**: The `{tool_name}` MCP tool failed during step: **{step_name}**

**Error Details**:
- **Error Type**: `{error_type}`
- **Error Message**: `{error_message}`{cause}

**Impact**: Commit procedure blocked at step: {step_name}. This is a blocker.

## Requirements

1. **Investigate**: Analyze error, check tool implementation, verify MCP
   protocol compliance
2. **Fix**: Resolve root cause, ensure tool works via MCP protocol
3. **Verify**: Test tool, verify commit procedure proceeds, ensure no regressions

## Implementation Steps

1. Analyze error type and message, check tool implementation
2. Fix root cause, add error handling/validation
3. Add tests for failure scenarios, verify fix works

## Success Criteria

- Root cause identified and fixed
- Tool works correctly via MCP protocol
- Commit procedure can proceed, no regressions

## Notes

Auto-generated on MCP tool failure. Tool: {tool_name}, Error:
{error_type}: {error_message}
"""


def _format_error_cause(error: Exception) -> str:
    """Format error cause string for plan template."""
    if error.__cause__:
        return f"\n\n**Caused by**: {type(error.__cause__).__name__}: {error.__cause__}"
    return ""


def generate_plan_content(tool_name: str, error: Exception, step_name: str) -> str:
    """Generate investigation plan content."""
    error_type = type(error).__name__
    error_message = str(error)
    today = datetime.now().strftime("%Y-%m-%d")
    cause = _format_error_cause(error)
    return _PLAN_TEMPLATE.format(
        tool_name=tool_name,
        step_name=step_name,
        today=today,
        error_type=error_type,
        error_message=error_message,
        cause=cause,
    )


async def create_investigation_plan(
    plans_dir: Path,
    project_root: Path,
    tool_name: str,
    error: Exception,
    step_name: str,
    ctx: MCPContext | None = None,
) -> Path:
    """Create an investigation plan file for a tool failure.

    Args:
        plans_dir: Directory where plan files are stored.
        project_root: Root directory of the project.
        tool_name: Name of the tool that failed.
        error: Exception that occurred.
        step_name: Commit procedure step where the failure occurred.
        ctx: Optional MCP context for client-visible logging.

    Returns:
        Path to the created plan file.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = tool_name.replace("\\", "/").split("/")[-1] or tool_name
    safe_tool = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_name).strip("-") or "tool"
    plan_filename = f"phase-investigate-{safe_tool}-failure-{timestamp}.md"
    plan_path = plans_dir / plan_filename
    plan_content = generate_plan_content(tool_name, error, step_name)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    _ = plan_path.write_text(plan_content, encoding="utf-8")
    rel = (
        plan_path.relative_to(project_root)
        if plan_path.is_relative_to(project_root)
        else plan_path
    )
    await log_client(ctx, "info", f"Created investigation plan: {rel}")
    logger.debug(f"Investigation plan details: {plan_path}")
    return plan_path


# ------------------------------------------------------------------
# Roadmap helpers
# ------------------------------------------------------------------


def _get_roadmap_path(project_root: Path) -> Path | None:
    """Get roadmap file path, or None if it does not exist."""
    roadmap_path = (
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        / MemoryBankFile.ROADMAP
    )
    if not roadmap_path.exists():
        logger.warning(f"Roadmap file not found: {roadmap_path}")
        return None
    return roadmap_path


def _ensure_blockers_section(content: str) -> str:
    """Ensure blockers section exists in roadmap content."""
    blockers_section = "## Blockers (ASAP Priority)"
    if blockers_section not in content:
        content += f"\n\n{blockers_section}\n\n"
    return content


def _get_relative_plan_path(plan_path: Path, project_root: Path) -> Path:
    """Return *plan_path* relative to *project_root* when possible."""
    try:
        return plan_path.relative_to(project_root)
    except ValueError:
        return plan_path


def _create_plan_entry(
    tool_name: str, relative_plan_path: Path, error: Exception
) -> str:
    """Create a formatted plan entry line for the roadmap."""
    return (
        f"- [Phase: Investigate {tool_name} MCP Tool Failure]"
        f"({relative_plan_path}) - ASAP (PLANNING) - Investigate and "
        f"fix MCP tool failure that occurred during commit procedure - "
        f"Tool: `{tool_name}`, Error: {type(error).__name__} - Impact: "
        f"Commit procedure blocked - Target completion: "
        f"{datetime.now().strftime('%Y-%m-%d')}\n"
    )


def _insert_plan_entry(content: str, plan_entry: str) -> str:
    """Insert *plan_entry* into roadmap *content*, deduplicating."""
    blockers_section = "## Blockers (ASAP Priority)"

    link_start = plan_entry.find("](")
    link_end = plan_entry.find(")", link_start + 2) if link_start != -1 else -1
    if link_start != -1 and link_end != -1:
        plan_path_fragment = plan_entry[link_start + 2 : link_end].strip()
        if plan_path_fragment:
            for line in content.split("\n"):
                stripped = line.strip()
                if (
                    stripped.startswith("- [Phase: Investigate ")
                    and plan_path_fragment in stripped
                ):
                    return content

    if plan_entry.strip() in content:
        return content

    insert_pos = content.find(blockers_section) + len(blockers_section)
    return content[:insert_pos] + "\n" + plan_entry + content[insert_pos:]


async def add_to_roadmap(
    project_root: Path,
    plan_path: Path,
    tool_name: str,
    error: Exception,
    ctx: MCPContext | None = None,
) -> None:
    """Add investigation plan to roadmap as blocker.

    Args:
        project_root: Root directory of the project.
        plan_path: Path to the investigation plan file.
        tool_name: Name of the tool that failed.
        error: Exception that occurred.
        ctx: Optional MCP context for client-visible logging.
    """
    roadmap_path = _get_roadmap_path(project_root)
    if not roadmap_path:
        rel = (
            plan_path.relative_to(project_root)
            if plan_path.is_relative_to(project_root)
            else plan_path
        )
        await log_client(
            ctx,
            "warning",
            f"Roadmap file not found; investigation plan created at: {rel}",
        )
        return

    roadmap_content = roadmap_path.read_text(encoding="utf-8")
    roadmap_content = _ensure_blockers_section(roadmap_content)
    relative_plan_path = _get_relative_plan_path(plan_path, project_root)
    plan_entry = _create_plan_entry(tool_name, relative_plan_path, error)
    roadmap_content = _insert_plan_entry(roadmap_content, plan_entry)

    _ = roadmap_path.write_text(roadmap_content, encoding="utf-8")
    await log_client(
        ctx, "info", f"Added investigation plan to roadmap: {relative_plan_path}"
    )
    logger.debug(f"Roadmap update details: {plan_path}")


def generate_user_notification(
    tool_name: str,
    error: Exception,
    step_name: str,
    plan_path: Path,
    project_root: Path,
) -> str:
    """Generate user notification for a tool failure.

    Args:
        tool_name: Name of the tool that failed.
        error: Exception that occurred.
        step_name: Commit procedure step where the failure occurred.
        plan_path: Path to investigation plan.
        project_root: Root directory of the project.

    Returns:
        User notification message.
    """
    error_type = type(error).__name__
    error_message = str(error)
    relative_plan_path = _get_relative_plan_path(plan_path, project_root)

    return f"""## ⚠️ MCP Tool Failure Detected

**Tool**: `{tool_name}`
**Step**: {step_name}
**Error Type**: {error_type}
**Error Message**: {error_message}

**Impact**: Commit procedure was blocked at step: {step_name}

**Fix Recommendation**: **FIX-ASAP** priority - Tool must be fixed before
commit can proceed

**Investigation Plan**: {relative_plan_path}

**Next Steps**:
1. Review the investigation plan
2. Investigate and fix the tool failure
3. Verify the fix works via MCP protocol
4. Re-run commit procedure after fix

**Protocol**: Commit procedure stopped immediately per MCP Tool Failure
protocol. No workarounds or fallbacks allowed."""
