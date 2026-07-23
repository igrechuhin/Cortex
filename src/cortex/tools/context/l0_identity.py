"""L0 identity layer builder."""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.context.layers import ContextConfig, ContextLayer, LayerResult
from cortex.tools.context.relevance_ranking import reorder_by_relevance


def _count_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _truncate_to_budget(text: str, budget: int, query: str | None = None) -> str:
    if _count_tokens(text) <= budget:
        return text
    # AI: reorder lines by relevance to the session goal before the word-cut
    # so the most relevant identity lines survive the drop-from-end budget
    # cut; no-op (returns lines unchanged) when ranking is disabled/unavailable.
    lines = reorder_by_relevance(query, text.split("\n"))
    words = "\n".join(lines).split()
    while words and int(len(words) * 1.3) > budget:
        _ = words.pop()
    return " ".join(words)


@lru_cache(maxsize=1)
def _load_project_identity(pyproject_path: Path) -> tuple[str, str]:
    project_name = "unknown-project"
    stack = "python"
    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError:
        return project_name, stack
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("name = ") and project_name == "unknown-project":
            project_name = stripped.split("=", 1)[1].strip().strip('"')
        if stripped.startswith("requires-python"):
            stack = f"python {stripped.split('=', 1)[1].strip().strip('\"')}"
    return project_name, stack


def _read_last_commit_summary(project_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _read_primary_goal(project_root: Path) -> str:
    goal_path = (
        get_cortex_path(project_root, CortexResourceType.SESSION) / "session-goal.md"
    )
    try:
        lines = goal_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return " ".join(lines[:2]).strip()


def _build_identity_lines(project_root: Path, primary_goal: str) -> list[str]:
    project_name, stack = _load_project_identity(project_root / "pyproject.toml")
    commit = _read_last_commit_summary(project_root)
    return [
        "Project identity",
        f"Project: {project_name}",
        f"Stack: {stack}",
        f"Primary goal: {primary_goal or 'not set'}",
        f"Last commit: {commit or 'unavailable'}",
    ]


async def build_l0(project_root: Path, config: ContextConfig) -> LayerResult:
    primary_goal = _read_primary_goal(project_root)
    raw_content = "\n".join(_build_identity_lines(project_root, primary_goal)).strip()
    content = _truncate_to_budget(
        raw_content, config.max_l0_tokens, query=primary_goal or None
    )
    return LayerResult(
        layer=ContextLayer.IDENTITY,
        tokens_estimate=_count_tokens(content),
        content=content,
        sources=["pyproject.toml", ".cortex/.session/session-goal.md"],
    )
