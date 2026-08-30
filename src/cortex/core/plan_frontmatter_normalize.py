"""Rewrite plan frontmatter into the canonical schema.

The graph parser tolerates quoted statuses, legacy status spellings and
``depends_on`` entries carrying a ``.md`` extension or directory prefix, but
those forms still break every other consumer that reads the YAML literally.
This module rewrites them in place so the files match the documented schema.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from cortex.core.artifact_graph import (
    normalize_plan_slug,
    resolve_plan_status_token,
)
from cortex.core.models._enums import PlanExecutionMode

_STATUS_LINE_RE = re.compile(
    r"^status\s*:\s*[\"']?(?P<value>[A-Za-z_]+).*$", re.IGNORECASE | re.MULTILINE
)
_DEPENDS_LINE_RE = re.compile(
    r"^depends_on\s*:\s*\[(?P<items>.*?)\][ \t]*(?:#.*)?$", re.IGNORECASE | re.MULTILINE
)
_EXECUTION_LINE_RE = re.compile(
    r"^execution\s*:\s*[\"']?(?P<value>[A-Za-z_]+)[\"']?[ \t]*(?:#.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
# AI: enum-valued keys and `created` are bare words; only free text keeps its
# quotes. An unquoted ISO date loads as a real date instead of a str, and a
# typo then fails loudly at parse time rather than passing as a string.
_CREATED_PATTERN = r"^created\s*:\s*[\"']?(?P<value>[0-9]{2,4}-[0-9]{1,2}-[0-9]{1,2})[\"']?[ \t]*(?:#.*)?$"
_CREATED_LINE_RE = re.compile(_CREATED_PATTERN, re.MULTILINE)
_ENUM_LINE_RE = re.compile(
    r"^(?P<key>work_type|priority)\s*:\s*[\"']?(?P<value>[A-Za-z][\w-]*)[\"']?[ \t]*(?:#.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_ENUM_VALUES: dict[str, frozenset[str]] = {
    "work_type": frozenset(
        {
            "fix",
            "refactor",
            "feature",
            "optimize",
            "docs",
            "infrastructure",
            "migration",
            "investigation",
            "security",
        }
    ),
    "priority": frozenset({"Blocker", "Critical", "High", "Medium", "Low"}),
}
# AI: legacy spellings mapped onto the canonical value, keyed by lowercase.
_ENUM_ALIASES: dict[str, dict[str, str]] = {
    "work_type": {
        "bug-fix": "fix",
        "bugfix": "fix",
        "blocker": "fix",
        "cleanup": "refactor",
        "documentation": "docs",
        "enhancement": "feature",
        "governance": "infrastructure",
        "improvement": "feature",
        "infra": "infrastructure",
        "internal_tooling": "infrastructure",
        "ops": "infrastructure",
        "quality": "fix",
        "refactoring": "refactor",
        "remediation": "fix",
        "tooling": "infrastructure",
    },
    "priority": {
        "normal": "Medium",
        "p0": "Critical",
        "p1": "High",
        "p2": "Medium",
    },
}


def _frontmatter_span(content: str) -> tuple[int, int] | None:
    """Return (start, end) offsets of the first YAML frontmatter body."""
    if not content.startswith("---"):
        return None
    first = content.find("\n")
    if first == -1:
        return None
    end = content.find("\n---", first)
    if end == -1:
        return None
    return first + 1, end + 1


def _normalized_created_line(match: re.Match[str]) -> str:
    """Expand a two-digit year, zero-pad, and unquote a plan ``created`` date."""
    year, month, day = match.group("value").split("-")
    if len(year) == 2:
        year = f"20{year}"
    try:
        parsed = date.fromisoformat(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
    except ValueError:
        # AI: surface an unparseable date rather than rewriting it into a guess.
        return match.group(0)
    return f"created: {parsed.isoformat()}"


def _normalized_status_line(match: re.Match[str]) -> str:
    # AI: leave unknown statuses (e.g. NOT_VIABLE) untouched rather than
    # rewriting them to the PENDING fallback and losing the author's intent.
    status = resolve_plan_status_token(match.group("value"))
    if status is None:
        return match.group(0)
    return f"status: {status.value}"


def _canonical_enum_value(key: str, value: str) -> str:
    """Map a raw enum value onto its canonical spelling, or return it unchanged."""
    lowered = value.lower()
    aliased = _ENUM_ALIASES[key].get(lowered)
    if aliased is not None:
        return aliased
    for known in _ENUM_VALUES[key]:
        if known.lower() == lowered:
            return known
    return value


def _normalized_enum_line(match: re.Match[str]) -> str:
    """Drop quotes from an enum-valued key, canonicalizing known spellings."""
    key = match.group("key").lower()
    return f"{key}: {_canonical_enum_value(key, match.group('value'))}"


def _normalized_depends_line(match: re.Match[str]) -> str:
    items = match.group("items").strip()
    if not items:
        return "depends_on: []"
    slugs = [normalize_plan_slug(item) for item in items.split(",")]
    joined = ", ".join(f'"{slug}"' for slug in slugs if slug)
    return f"depends_on: [{joined}]"


def _normalized_execution_line(match: re.Match[str]) -> str:
    raw = match.group("value").strip().lower()
    for candidate in PlanExecutionMode:
        if candidate.value == raw:
            return f"execution: {candidate.value}"
    return match.group(0)


def normalize_plan_frontmatter(content: str) -> str:
    """Return ``content`` with a canonical status, depends_on and execution."""
    span = _frontmatter_span(content)
    if span is None:
        return content
    start, end = span
    head, body, tail = content[:start], content[start:end], content[end:]
    body = _STATUS_LINE_RE.sub(_normalized_status_line, body, count=1)
    body = _DEPENDS_LINE_RE.sub(_normalized_depends_line, body, count=1)
    body = _EXECUTION_LINE_RE.sub(_normalized_execution_line, body, count=1)
    body = _ENUM_LINE_RE.sub(_normalized_enum_line, body)
    body = _CREATED_LINE_RE.sub(_normalized_created_line, body, count=1)
    return head + body + tail


def normalize_plan_files(plans_dir: Path) -> list[Path]:
    """Normalize every plan file under ``plans_dir``; return the changed ones."""
    if not plans_dir.is_dir():
        return []
    changed: list[Path] = []
    for path in sorted(plans_dir.rglob("*.md")):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = normalize_plan_frontmatter(content)
        if updated == content:
            continue
        try:
            _ = path.write_text(updated, encoding="utf-8")
        except OSError:
            continue
        changed.append(path)
    return changed
