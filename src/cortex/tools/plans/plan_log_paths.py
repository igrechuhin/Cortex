"""
Shared resolution and injection helpers for plan input logs.

Two upstream prompts feed `plan(operation="create")`:

- `explore.md` writes an explore decision log and passes ``explore_log_path``
- `shape.md` writes a shaping record and passes ``shape_log_path``

Both paths share one validator so containment rules cannot drift between them.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "PlanLogPathError",
    "extract_markdown_section",
    "inject_decision_basis_from_explore_log",
    "inject_shaping_constraints_from_shape_log",
    "resolve_plan_log_path",
]


class PlanLogPathError(ValueError):
    """Raised when an explore/shape log path escapes the project root."""


def resolve_plan_log_path(
    project_root: Path,
    raw_path: str,
    *,
    parameter_name: str,
) -> Path:
    """Resolve a project-relative log path, rejecting traversal and escapes.

    Args:
        project_root: Repository root the path must stay inside.
        raw_path: Caller-supplied path, expected to be project-relative.
        parameter_name: Tool parameter name, used in the error message.

    Returns:
        The resolved absolute path (which may not exist yet).

    Raises:
        PlanLogPathError: If the path is absolute or resolves outside the root.
    """
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise PlanLogPathError(
            f"{parameter_name} must be project-relative, got absolute path: {raw_path}"
        )
    root = project_root.resolve()
    # AI: resolve() first so symlinks and `..` segments are normalized before
    # the containment check; a pure string prefix test would miss both.
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise PlanLogPathError(
            f"{parameter_name} must stay within the project root: {raw_path}"
        )
    return resolved


def extract_markdown_section(markdown: str, heading: str) -> str | None:
    """Return the body of a `## Heading` section, or None when absent/empty."""
    in_section = False
    section_lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped == heading:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section:
            section_lines.append(line)
    content = "\n".join(section_lines).strip()
    return content or None


def _read_log_text(
    project_root: Path, raw_path: str, parameter_name: str
) -> str | None:
    """Resolve and read a log file; None when it is missing or unreadable."""
    log_path = resolve_plan_log_path(
        project_root, raw_path, parameter_name=parameter_name
    )
    try:
        if not log_path.is_file():
            return None
        return log_path.read_text(encoding="utf-8")
    except OSError:
        return None


def inject_decision_basis_from_explore_log(
    project_root: Path,
    plan_content: str,
    explore_log_path: str | None,
) -> str:
    """Prepend a `## Decision Basis` section derived from an explore log."""
    if not explore_log_path:
        return plan_content
    log_text = _read_log_text(project_root, explore_log_path, "explore_log_path")
    if log_text is None:
        return plan_content
    decision_basis = _build_decision_basis(log_text, explore_log_path)
    if not decision_basis:
        return plan_content
    return f"{decision_basis}\n\n{plan_content}"


def _build_decision_basis(log_text: str, explore_log_path: str) -> str:
    selected = extract_markdown_section(log_text, "## Selected Option")
    recommendation = extract_markdown_section(log_text, "## Recommendation")
    if not selected and not recommendation:
        return ""
    parts: list[str] = [
        "## Decision Basis",
        f"- Explore log: `{explore_log_path}`",
    ]
    if selected:
        parts.append(f"- Selected option: {selected.splitlines()[0].strip()}")
    if recommendation:
        parts.append(f"- Recommendation: {recommendation.splitlines()[0].strip()}")
    return "\n".join(parts)


def inject_shaping_constraints_from_shape_log(
    project_root: Path,
    plan_content: str,
    shape_log_path: str | None,
) -> str:
    """Prepend a `## Shaping Constraints` section derived from a shaping record."""
    if not shape_log_path:
        return plan_content
    log_text = _read_log_text(project_root, shape_log_path, "shape_log_path")
    if log_text is None:
        return plan_content
    constraints = _build_shaping_constraints(log_text, shape_log_path)
    if not constraints:
        return plan_content
    return f"{constraints}\n\n{plan_content}"


def _build_shaping_constraints(log_text: str, shape_log_path: str) -> str:
    """Render resolved shaping decisions as fixed, non-re-derivable constraints."""
    decisions = extract_markdown_section(log_text, "## Resolved Decisions")
    if not decisions:
        # AI: Resolved Decisions is the load-bearing section; without it the
        # record is malformed and must not silently weaken the generated plan.
        return ""
    parts: list[str] = [
        "## Shaping Constraints",
        "",
        f"Resolved during shaping (`{shape_log_path}`)."
        + " Treat these as fixed constraints, not choices to re-derive.",
        "",
        "### Resolved Decisions",
        "",
        decisions,
    ]
    parts.extend(_optional_shaping_block(log_text, "## Assumptions", "Assumptions"))
    parts.extend(
        _optional_shaping_block(
            log_text, "## Explicitly Out of Scope", "Explicitly Out of Scope"
        )
    )
    return "\n".join(parts)


def _optional_shaping_block(log_text: str, heading: str, title: str) -> list[str]:
    body = extract_markdown_section(log_text, heading)
    if not body:
        return []
    return ["", f"### {title}", "", body]
