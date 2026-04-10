"""Build SessionGoal anchors from user input and optional plan files."""

from __future__ import annotations

from pathlib import Path

from cortex.core.plan_path_extract import extract_file_patterns_from_plan
from cortex.core.session_goal_models import SessionGoal


def resolve_plan_file(project_root: Path, plan_slug: str | None) -> Path | None:
    """Resolve plan_slug to a readable file under `.cortex/plans/`."""
    if not plan_slug or not str(plan_slug).strip():
        return None
    raw = str(plan_slug).strip()
    path = Path(raw)
    if path.is_absolute():
        return path if path.is_file() else None
    if raw.startswith(".cortex/"):
        candidate = project_root / raw
        return candidate if candidate.is_file() else None
    plans_dir = project_root / ".cortex" / "plans"
    direct = plans_dir / raw
    if direct.is_file():
        return direct
    # Allow slug without .md
    if not raw.endswith(".md"):
        with_md = plans_dir / f"{raw}.md"
        if with_md.is_file():
            return with_md
    return None


def build_session_goal(
    goal_text: str,
    plan_slug: str | None,
    project_root: Path,
    blocked_files: list[str] | None = None,
) -> SessionGoal:
    """Create a SessionGoal with allowed_files from plan content when available."""
    allowed: list[str] = []
    resolved = resolve_plan_file(project_root, plan_slug)
    if resolved is not None and resolved.is_file():
        try:
            text = resolved.read_text(encoding="utf-8")
        except OSError:
            text = ""
        allowed = extract_file_patterns_from_plan(text)
    return SessionGoal(
        goal=goal_text.strip(),
        plan_slug=plan_slug.strip() if plan_slug else None,
        allowed_files=allowed,
        blocked_files=list(blocked_files or []),
    )
