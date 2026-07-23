"""Self-test validation for propose_framework_optimization changed files.

Scope (per plan): JSON structural validation for config/manifest JSON,
YAML-frontmatter validation for ``.mdc`` rules and prompt ``.md`` files, and a
scoped file-size check mirroring the real quality gate's file-size limit.
This is schema/structure-only — it is explicitly not a substitute for human
review of behavioral impact (see plan's Risks table).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import yaml

from cortex.core.constants import MAX_FILE_LINES
from cortex.tools.plans.step_draft_core import split_frontmatter


def _frontmatter_body(frontmatter: str) -> str:
    lines = frontmatter.splitlines()
    if len(lines) < 2:
        return ""
    return "\n".join(lines[1:-1])


def _validate_json_file(path: Path) -> str | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"{path.name}: invalid JSON ({exc})"
    if not isinstance(parsed, dict):
        return f"{path.name}: JSON root must be an object"
    return None


def _validate_frontmatter_file(path: Path, *, require_description: bool) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"{path.name}: unreadable ({exc})"
    frontmatter, _ = split_frontmatter(text)
    if frontmatter is None:
        if require_description:
            return f"{path.name}: missing YAML frontmatter"
        return None
    try:
        parsed = yaml.safe_load(_frontmatter_body(frontmatter))
    except yaml.YAMLError as exc:
        return f"{path.name}: malformed frontmatter YAML ({exc})"
    if not isinstance(parsed, dict):
        return f"{path.name}: frontmatter must be a YAML mapping"
    mapping = cast("dict[str, object]", parsed)
    if require_description and not str(mapping.get("description", "")).strip():
        return f"{path.name}: frontmatter must include non-empty description"
    return None


def _validate_file_size(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as handle:
            line_count = sum(1 for _ in handle)
    except OSError as exc:
        return f"{path.name}: unreadable ({exc})"
    if line_count > MAX_FILE_LINES:
        return f"{path.name}: exceeds {MAX_FILE_LINES}-line limit ({line_count} lines)"
    return None


def self_test_one_file(path: Path) -> str | None:
    """Run schema/frontmatter/size self-test on one changed worktree file."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        reason = _validate_json_file(path)
    elif suffix == ".mdc":
        reason = _validate_frontmatter_file(path, require_description=True)
    elif suffix == ".md":
        reason = _validate_frontmatter_file(path, require_description=False)
    else:
        reason = None
    if reason is not None:
        return reason
    return _validate_file_size(path)


def run_self_test(changed_paths: list[Path]) -> str | None:
    """Run self-test across all changed files; return first failure reason or None."""
    for path in changed_paths:
        reason = self_test_one_file(path)
        if reason is not None:
            return reason
    return None
