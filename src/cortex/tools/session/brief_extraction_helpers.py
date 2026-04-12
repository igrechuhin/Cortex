"""Extraction and suggestion helpers for session brief building.

Extracted from brief to keep the main module under 400 lines.
"""

from __future__ import annotations

import re
from pathlib import Path

from cortex.tools.files.plan_draft_file_ops import count_stale_plan_drafts
from cortex.tools.session.models import (
    ConcurrentSession,
    GitStatusSummary,
    SessionHealthSummary,
    WikiStatusSummary,
)
from cortex.tools.session.wiki_status import append_session_wiki_init_hint
from cortex.validation.roadmap_progress_consistency import (
    check_roadmap_progress_consistency,
)


def extract_focus_and_completed(content: str) -> tuple[str, list[str]]:
    """Extract current focus and recent completed from activeContext content."""
    return extract_current_focus(content), extract_recent_completed(content)


def extract_current_focus(active_context_content: str) -> str:
    """Extract current focus from activeContext.md."""
    from cortex.tools.files.section_helpers import extract_section_from_content

    section_content, warning = extract_section_from_content(
        active_context_content, "## Current Focus"
    )
    if warning or not section_content:
        return ""
    lines = section_content.split("\n")
    if lines and lines[0].strip().startswith("#"):
        return "\n".join(lines[1:]).strip()
    return section_content.strip()


def extract_recent_completed(
    active_context_content: str, max_items: int = 5
) -> list[str]:
    """Extract recent completed items from activeContext.md."""
    completed_items: list[str] = []
    lines = active_context_content.split("\n")
    in_completed_section = False
    for line in lines:
        if line.strip().startswith("## Completed Work"):
            in_completed_section = True
            continue
        if in_completed_section:
            if line.strip().startswith("##") and not line.strip().startswith("###"):
                break
            if line.strip().startswith("- ✅") or line.strip().startswith("- **"):
                item_text = line.strip()
                item_text = re.sub(r"^-\s*(✅\s*)?\*\*", "", item_text)
                item_text = re.sub(r"\*\*\s*-.*$", "", item_text)
                item_text = item_text.strip()
                if item_text:
                    completed_items.append(item_text)
                    if len(completed_items) >= max_items:
                        break
    return completed_items


def add_concurrency_suggestions(
    suggestions: list[str],
    locked_tasks: list[str] | None,
    concurrent_sessions: list[ConcurrentSession] | None,
) -> None:
    """Add suggestions about concurrent sessions and locked tasks."""
    if concurrent_sessions:
        session_count = len(concurrent_sessions)
        suggestions.append(
            f"{session_count} concurrent session(s) active — check locked_tasks to avoid duplicate work"
        )
    if locked_tasks:
        if len(locked_tasks) == 1:
            suggestions.append(f"Task locked by another session: {locked_tasks[0]}")
        else:
            suggestions.append(
                f"{len(locked_tasks)} tasks locked by other sessions — see locked_tasks field"
            )


def add_mcp_and_git_suggestions(
    suggestions: list[str],
    mcp_healthy: bool,
    git_status: GitStatusSummary | None,
) -> None:
    """Append MCP and git-related suggestions."""
    if not mcp_healthy:
        suggestions.append(
            "Cortex MCP is disconnected or unhealthy. Reconnect the MCP server and "
            + "re-run this command; do not proceed without MCP."
        )
    if git_status and git_status.has_uncommitted_changes:
        suggestions.append(
            f"You have uncommitted changes ({git_status.modified_files_count} modified, "
            + f"{git_status.untracked_files_count} untracked) — consider committing first"
        )


def add_budget_and_missing_suggestions(
    suggestions: list[str], health: SessionHealthSummary
) -> None:
    """Append token budget and missing-files suggestions."""
    if health.token_budget_status == "over_budget":
        suggestions.append(
            f"Token budget exceeded ({health.total_tokens} tokens) — consider compaction"
        )
    elif health.token_budget_status == "warning":
        suggestions.append(
            f"Token budget at {health.total_tokens / 80000 * 100:.0f}% — consider compaction"
        )
    if health.missing_files:
        suggestions.append(
            f"Missing required files: {', '.join(health.missing_files)} — run initialization"
        )


def add_stale_plan_draft_suggestions(
    suggestions: list[str], project_root: Path | None
) -> None:
    """Surface old step-by-step plan drafts so agents can list or discard them."""
    if project_root is None:
        return
    stale = count_stale_plan_drafts(project_root)
    if stale <= 0:
        return
    suggestions.append(
        f"{stale} stale plan draft(s) older than 48h — call manage_file with operation "
        + "list_drafts to inspect them, or operation discard_draft with JSON content "
        + "that includes a plan_slug string to delete one draft file."
    )


def add_memory_bank_sync_suggestions(
    suggestions: list[str],
    progress_content: str,
    roadmap_content: str,
) -> None:
    """Append memory-bank sync warnings for unresolved PARTIAL entries."""
    violations = check_roadmap_progress_consistency(progress_content, roadmap_content)
    for violation in violations:
        suggestions.append(f"⚠️ Memory-bank sync: {violation}")


def generate_session_suggestions(
    health: SessionHealthSummary,
    git_status: GitStatusSummary | None,
    next_work_item: str | None,
    locked_tasks: list[str] | None = None,
    concurrent_sessions: list[ConcurrentSession] | None = None,
    mcp_healthy: bool = True,
    progress_content: str = "",
    roadmap_content: str = "",
    wiki_status: WikiStatusSummary | None = None,
    project_root: Path | None = None,
) -> list[str]:
    """Generate actionable suggestions for the session."""
    suggestions: list[str] = []
    add_mcp_and_git_suggestions(suggestions, mcp_healthy, git_status)
    add_budget_and_missing_suggestions(suggestions, health)
    add_concurrency_suggestions(suggestions, locked_tasks, concurrent_sessions)
    add_memory_bank_sync_suggestions(suggestions, progress_content, roadmap_content)
    append_session_wiki_init_hint(suggestions, wiki_status, project_root)
    add_stale_plan_draft_suggestions(suggestions, project_root)
    if next_work_item:
        suggestions.append(f"Next roadmap item: {next_work_item}")
    else:
        suggestions.append(
            "Use `/cortex/explore` before `/cortex/plan` for complex or novel tasks."
        )
    return suggestions
