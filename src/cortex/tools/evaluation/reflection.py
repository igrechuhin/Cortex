"""Optional reflection (critic) pass for the quality gate — heuristic diff review."""

from __future__ import annotations

import json
import re
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field

from cortex.core.models import JsonValue, ModelDict
from cortex.core.session_config import read_session_config
from cortex.tools.execution.pre_commit_config import as_bool
from cortex.tools.reflection_constants import (
    build_reflection_checklist_markdown,
    detect_languages_in_diff,
)


class CritiqueCategory(StrEnum):
    """Category for a single critique item."""

    LOGIC = "logic"
    SECURITY = "security"
    EDGE_CASE = "edge_case"
    TEST_COVERAGE = "test_coverage"
    DOCS = "docs"


class CritiqueSeverity(StrEnum):
    """Severity for a critique item."""

    WARNING = "warning"
    ERROR = "error"


class CritiqueItem(BaseModel):
    """One structured issue identified by the reflection pass."""

    category: CritiqueCategory
    severity: CritiqueSeverity
    location: str = Field(
        ...,
        description="File path, hunk, or 'diff' when not file-specific.",
    )
    description: str
    suggestion: str


class ReflectionResult(BaseModel):
    """Aggregated output of analyzing a diff against gate output and rules."""

    items: list[CritiqueItem]
    score: int = Field(..., ge=0, le=100)
    summary: str
    approved: bool


def collect_git_diff_text(project_root: Path, max_bytes: int = 512_000) -> str:
    """Return `git diff HEAD` text, truncated if larger than ``max_bytes``."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            cwd=str(project_root),
            timeout=60,
            text=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
    if result.returncode != 0:
        return ""
    raw = result.stdout.decode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        return raw[:max_bytes] + "\n... [diff truncated for reflection]\n"
    return raw


def _diff_has_try_without_except_or_finally(diff_text: str) -> bool:
    """Heuristic: added `try:` with no added `except` or `finally` in the diff."""
    if "try:" not in diff_text:
        return False
    if "+except" in diff_text or "+finally" in diff_text:
        return False
    return (
        "+try:" in diff_text
        or re.search(r"^\+\s*try:\s*$", diff_text, re.MULTILINE) is not None
    )


_TODO_MARKERS = ("TODO", "FIXME", "XXX", "HACK")


_SECRET_LIKE = re.compile(
    r"(?i)(password|api[_-]?key|secret|token)\s*=\s*['\"][^'\"]{3,}['\"]"
)
_DICT_ACCESS_RE = re.compile(r"\b(?P<name>[A-Za-z_]\w*)\[(?:\"|')")
_CHAINED_ATTR_RE = re.compile(r"\b[A-Za-z_]\w*\.\w+\.\w+\b")
_TYPED_DICT_CLASS_RE = re.compile(
    r"^\s*class\s+(?P<name>[A-Za-z_]\w*)\s*\(\s*TypedDict\s*\)\s*:"
)
_TYPED_DICT_FACTORY_RE = re.compile(r"^\s*(?P<name>[A-Za-z_]\w*)\s*=\s*TypedDict\s*\(")
_ANNOTATED_NAME_RE = re.compile(
    r"\b(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[A-Za-z_]\w*)\b"
)


def _collect_per_line_items(diff_text: str) -> list[CritiqueItem]:
    """Single-pass collector for TODO/FIXME markers and secret-like literals."""
    items: list[CritiqueItem] = []
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        upper = body.upper()
        if any(m in upper for m in _TODO_MARKERS):
            items.append(
                CritiqueItem(
                    category=CritiqueCategory.DOCS,
                    severity=CritiqueSeverity.WARNING,
                    location="diff",
                    description="Added line contains a TODO/FIXME-style marker.",
                    suggestion="Resolve or track the marker before merge.",
                )
            )
        if _SECRET_LIKE.search(body):
            items.append(
                CritiqueItem(
                    category=CritiqueCategory.SECURITY,
                    severity=CritiqueSeverity.ERROR,
                    location="diff",
                    description="Possible hardcoded credential or secret-like literal in added line.",
                    suggestion="Use environment variables, a secrets manager, or configuration — not literals.",
                )
            )
    return items


def _stale_belief_item(location: str) -> CritiqueItem:
    return CritiqueItem(
        category=CritiqueCategory.DOCS,
        severity=CritiqueSeverity.WARNING,
        location=location,
        description=(
            "BELIEF annotation may be stale: a `# BELIEF:` line appears "
            "unchanged in the hunk while other lines changed."
        ),
        suggestion="Review the BELIEF against the new behavior and update or remove it.",
    )


def _belief_stale_items_for_python(diff_text: str) -> list[CritiqueItem]:
    """Warn when a hunk edits code but leaves a ``# BELIEF:`` line unchanged as context."""
    items: list[CritiqueItem] = []
    current_file = ""
    hunk_lines: list[str] = []

    def flush_hunk() -> None:
        nonlocal hunk_lines
        if (
            current_file.endswith(".py")
            and hunk_lines
            and _hunk_has_stale_belief_context(hunk_lines)
        ):
            items.append(_stale_belief_item(current_file))
        hunk_lines = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush_hunk()
            current_file = ""
        elif line.startswith("+++ b/"):
            flush_hunk()
            current_file = line[6:].strip()
        elif line.startswith("@@"):
            flush_hunk()
        elif current_file.endswith(".py"):
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                continue
            if len(line) >= 2 and line[0] in " +-" and not line.startswith("\\"):
                hunk_lines.append(line)
    flush_hunk()
    return items


def _hunk_has_stale_belief_context(hunk_lines: list[str]) -> bool:
    """True if an unchanged BELIEF line sits in a hunk that also edits other lines."""
    belief_marker = "# BELIEF:"
    has_context_belief = False
    has_other_change = False
    for line in hunk_lines:
        if len(line) < 2:
            continue
        kind, rest = line[0], line[1:]
        if kind == " " and belief_marker in rest:
            has_context_belief = True
        elif kind in "+-":
            if belief_marker in rest:
                continue
            has_other_change = True
    return has_context_belief and has_other_change


def _maybe_untested_public(diff_text: str) -> list[CritiqueItem]:
    """Warn when new defs appear under src/ but no test file changes in the diff."""
    items: list[CritiqueItem] = []
    if "src/" not in diff_text:
        return items
    if "/tests/" in diff_text or "tests/" in diff_text:
        return items
    if re.search(r"^\+\s*def\s+\w+\s*\(", diff_text, re.MULTILINE):
        items.append(
            CritiqueItem(
                category=CritiqueCategory.TEST_COVERAGE,
                severity=CritiqueSeverity.WARNING,
                location="diff",
                description="Added function(s) under src/ with no test path changes in the same diff.",
                suggestion="Add or update unit tests covering new or changed behavior.",
            )
        )
    return items


def _mid_function_belief_item(location: str, pattern_label: str) -> CritiqueItem:
    return CritiqueItem(
        category=CritiqueCategory.DOCS,
        severity=CritiqueSeverity.WARNING,
        location=location,
        description=(
            f"Added Python code uses {pattern_label} that assumes external data shape."
        ),
        suggestion=(
            "Add a `# BELIEF:` annotation if this access depends on external or "
            "optional-shaped data having the expected fields."
        ),
    )


def _typed_dict_bindings(lines: list[str]) -> set[str]:
    typed_dict_types: set[str] = set()
    for line in lines:
        body = line[1:] if line and line[0] in " +-" else line
        if match := _TYPED_DICT_CLASS_RE.match(body):
            typed_dict_types.add(match.group("name"))
        elif match := _TYPED_DICT_FACTORY_RE.match(body):
            typed_dict_types.add(match.group("name"))

    bindings: set[str] = set()
    for line in lines:
        body = line[1:] if line and line[0] in " +-" else line
        for match in _ANNOTATED_NAME_RE.finditer(body):
            if match.group("type") in typed_dict_types:
                bindings.add(match.group("name"))
    return bindings


def _python_diff_files(diff_text: str) -> list[tuple[str, list[str]]]:
    files: list[tuple[str, list[str]]] = []
    current_file = ""
    file_lines: list[str] = []

    def flush_file() -> None:
        nonlocal file_lines
        if current_file.endswith(".py") and file_lines:
            files.append((current_file, file_lines))
        file_lines = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush_file()
            current_file = ""
        elif line.startswith("+++ b/"):
            flush_file()
            current_file = line[6:].strip()
        elif current_file.endswith(".py"):
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                continue
            if len(line) >= 2 and line[0] in " +-" and not line.startswith("\\"):
                file_lines.append(line)
    flush_file()
    return files


def _risky_access_items_for_file(
    location: str, file_lines: list[str]
) -> list[CritiqueItem]:
    items: list[CritiqueItem] = []
    typed_dict_bindings = _typed_dict_bindings(file_lines)
    fired_patterns: set[str] = set()
    for line in file_lines:
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        if (
            "dict_access" not in fired_patterns
            and (match := _DICT_ACCESS_RE.search(body)) is not None
            and match.group("name") not in typed_dict_bindings
        ):
            items.append(_mid_function_belief_item(location, "raw dict key access"))
            fired_patterns.add("dict_access")
        if (
            "chained_attr" not in fired_patterns
            and _CHAINED_ATTR_RE.search(body) is not None
        ):
            items.append(
                _mid_function_belief_item(location, "chained attribute access")
            )
            fired_patterns.add("chained_attr")
        if len(fired_patterns) == 2:
            break
    return items


def _risky_mid_function_access(diff_text: str) -> list[CritiqueItem]:
    """Warn on added Python access patterns that suggest an unstated BELIEF."""
    items: list[CritiqueItem] = []
    for location, file_lines in _python_diff_files(diff_text):
        items.extend(_risky_access_items_for_file(location, file_lines))
    return items


def _score_items(items: list[CritiqueItem]) -> ReflectionResult:
    """Compute score, summary, and approval from a list of critique items."""
    error_n = sum(1 for i in items if i.severity == CritiqueSeverity.ERROR)
    warn_n = len(items) - error_n
    approved = error_n == 0
    score = max(0, min(100, 100 - 20 * error_n - 5 * warn_n))
    if approved:
        summary = f"Heuristic reflection passed (score {score}). {warn_n} warning(s), 0 error-level finding(s)."
    else:
        summary = f"Heuristic reflection found {error_n} error-level issue(s) and {warn_n} warning(s) (score {score})."
    return ReflectionResult(
        items=items, score=score, summary=summary, approved=approved
    )


def _collect_diff_items(diff_text: str, langs: frozenset[str]) -> list[CritiqueItem]:
    """Collect all heuristic critique items for a diff."""
    items: list[CritiqueItem] = []
    if "python" in langs and _diff_has_try_without_except_or_finally(diff_text):
        items.append(
            CritiqueItem(
                category=CritiqueCategory.LOGIC,
                severity=CritiqueSeverity.ERROR,
                location="diff",
                description="Diff adds `try:` without `except` or `finally` in changed lines.",
                suggestion="Add exception handling or use `finally` as appropriate.",
            )
        )
    items.extend(_collect_per_line_items(diff_text))
    if "python" in langs:
        items.extend(_belief_stale_items_for_python(diff_text))
        items.extend(_risky_mid_function_access(diff_text))
        items.extend(_maybe_untested_public(diff_text))
    return items


def analyze_diff(
    diff_text: str,
    gate_output: str,
    rules_content: str,
    langs: frozenset[str] | None = None,
) -> ReflectionResult:
    """Run heuristic reflection over a diff and gate output.

    ``gate_output`` and ``rules_content`` are included for API symmetry and future
    LLM-backed analysis. Language-specific heuristics run only when the diff
    includes paths for those languages (see :func:`detect_languages_in_diff`).

    Pass pre-computed ``langs`` to avoid a redundant ``detect_languages_in_diff``
    call when the caller already holds the result.
    """
    _ = gate_output, rules_content  # reserved for structured/LLM pass
    if langs is None:
        langs = frozenset(detect_languages_in_diff(diff_text))
    return _score_items(_collect_diff_items(diff_text, langs))


class ReflectionConfig(BaseModel):
    """Typed view of reflection flags from pipeline or session config."""

    reflection: bool = False
    force_reflection: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> ReflectionConfig:
        return cls(
            reflection=as_bool(d.get("reflection"), False),
            force_reflection=as_bool(d.get("force_reflection"), False),
        )

    @property
    def enabled(self) -> bool:
        return self.reflection or self.force_reflection


def apply_reflection_to_gate_result(
    root: Path,
    result: ModelDict,
    cfg: dict[str, object],
) -> None:
    """If reflection is enabled and the gate passed, run reflection; may set preflight_passed False."""
    if not bool(result.get("preflight_passed")):
        return
    rc = ReflectionConfig.from_dict(cfg)
    if not rc.enabled:
        rc = ReflectionConfig.from_dict(dict(read_session_config()))
    if not rc.enabled:
        return

    diff_text = collect_git_diff_text(root)
    gate_blob = json.dumps(result, default=str)[:200_000]
    langs = detect_languages_in_diff(diff_text)
    checklist = build_reflection_checklist_markdown(langs)
    result["reflection_languages"] = cast(JsonValue, langs)
    rr = analyze_diff(diff_text, gate_blob, checklist, frozenset(langs))
    result["reflection_result"] = rr.model_dump(mode="json")
    if not rr.approved:
        result["preflight_passed"] = False
