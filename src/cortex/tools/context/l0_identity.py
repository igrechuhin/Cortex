"""L0 identity layer builder."""

from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import cast

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


# Build manifests in precedence order: (filename, project-name pattern, stack).
_MANIFESTS: tuple[tuple[str, str, str], ...] = (
    ("pyproject.toml", r'^\s*name\s*=\s*"([^"]+)"', "python"),
    ("Package.swift", r'^\s*name:\s*"([^"]+)"', "swift"),
    ("package.json", r'"name"\s*:\s*"([^"]+)"', "node"),
    ("Cargo.toml", r'^\s*name\s*=\s*"([^"]+)"', "rust"),
    ("go.mod", r"^module\s+(\S+)", "go"),
)

# Optional version refinement per stack, read from the same manifest.
_STACK_VERSION_PATTERNS: dict[str, str] = {
    "python": r'^\s*requires-python\s*=\s*"([^"]+)"',
    "swift": r"^//\s*swift-tools-version:\s*([\d.]+)",
}


def _refine_stack(stack: str, content: str) -> str:
    """Append the manifest's declared toolchain version when it states one."""
    pattern = _STACK_VERSION_PATTERNS.get(stack)
    if pattern is None:
        return stack
    match = re.search(pattern, content, re.MULTILINE)
    return f"{stack} {match.group(1)}" if match else stack


@lru_cache(maxsize=8)
def _load_project_identity(project_root: Path) -> tuple[str, str]:
    """Identify the project from its build manifest.

    Only pyproject.toml was consulted before, so every non-Python project was
    reported as `unknown-project` / `python` — pointing agents in a Swift repo
    at the wrong toolchain. An unrecognised project now says so.
    """
    for filename, name_pattern, stack in _MANIFESTS:
        try:
            content = (project_root / filename).read_text(encoding="utf-8")
        except OSError:
            continue
        match = re.search(name_pattern, content, re.MULTILINE)
        return (
            match.group(1) if match else project_root.name,
            _refine_stack(stack, content),
        )
    return project_root.name or "unknown-project", "unknown"


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
    """Read the session goal text.

    The file is JSON despite the .md suffix; joining its first two lines
    emitted a truncated `{ "goal": "...` fragment into every L0 layer.
    """
    goal_path = (
        get_cortex_path(project_root, CortexResourceType.SESSION) / "session-goal.md"
    )
    try:
        raw = goal_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        parsed: object = json.loads(raw)
    except json.JSONDecodeError:
        return " ".join(raw.splitlines()[:2]).strip()
    if not isinstance(parsed, dict):
        return ""
    goal: object = cast("dict[str, object]", parsed).get("goal")
    return str(goal).strip() if isinstance(goal, str) else ""


def _build_identity_lines(project_root: Path, primary_goal: str) -> list[str]:
    project_name, stack = _load_project_identity(project_root)
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
