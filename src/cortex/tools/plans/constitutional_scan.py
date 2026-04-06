"""Scan plan content against project constitution (memory bank)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from cortex.core.path_resolver import get_constitution_path

logger = logging.getLogger(__name__)

COMPLIANCE_SECTION_HEADER = "## Constitutional Compliance"

_SECTION_PATTERN = re.compile(
    r"^##\s+(Principles|Hard limits)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_bullet(line: str) -> str:
    """Remove leading list markers from a markdown line."""
    s = line.strip()
    return re.sub(r"^[-*]\s+", "", s).strip()


def extract_constitution_rule_lines(constitution_md: str) -> list[str]:
    """Pull rule bullets from key constitution sections."""
    lines = constitution_md.splitlines()
    rules: list[str] = []
    in_section = False
    for line in lines:
        if _SECTION_PATTERN.match(line.strip()):
            in_section = True
            continue
        if (
            in_section
            and line.startswith("## ")
            and not _SECTION_PATTERN.match(line.strip())
        ):
            in_section = False
        if not in_section:
            continue
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            text = _strip_bullet(stripped)
            if text and not text.startswith("<!--"):
                rules.append(text)
    return rules


def _violation_for_rule(rule: str, plan_md: str) -> str | None:
    """If plan text may violate rule, return a violation line; else None."""
    plan_lower = plan_md.lower()
    rule_stripped = rule.strip()
    if len(rule_stripped) < 4:
        return None
    lower_rule = rule_stripped.lower()
    if not lower_rule.startswith("no "):
        return None
    remainder = rule_stripped[3:].strip()
    if len(remainder) < 2:
        return None
    if remainder.lower() in plan_lower:
        return (
            f"[VIOLATION: {rule_stripped}] Plan text may reference a disallowed "
            f"concept: {remainder}"
        )
    return None


def find_potential_violations(rule_lines: list[str], plan_md: str) -> list[str]:
    """Return human-readable violation strings (may be empty)."""
    out: list[str] = []
    for rule in rule_lines:
        if v := _violation_for_rule(rule, plan_md):
            out.append(v)
    return out


def append_compliance_section(plan_md: str, violations: list[str]) -> str:
    """Append or replace the Constitutional Compliance section."""
    body = plan_md.rstrip()
    if COMPLIANCE_SECTION_HEADER in body:
        before, _, _ = body.partition(COMPLIANCE_SECTION_HEADER)
        body = before.rstrip()
    lines = [body, "", COMPLIANCE_SECTION_HEADER, ""]
    for v in violations:
        lines.append(f"- {v}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def apply_constitutional_compliance(
    project_root: Path, plan_md: str
) -> tuple[str, int]:
    """Augment plan markdown when the constitution flags potential issues.

    Returns:
        (possibly updated markdown, violation count)
    """
    path = get_constitution_path(project_root)
    if not path.is_file():
        return plan_md, 0
    try:
        constitution_md = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Constitution unreadable at %s: %s", path, e)
        return plan_md, 0
    rules = extract_constitution_rule_lines(constitution_md)
    violations = find_potential_violations(rules, plan_md)
    if not violations:
        return plan_md, 0
    logger.warning(
        "Constitutional compliance: %d potential violation(s) for new plan",
        len(violations),
    )
    return append_compliance_section(plan_md, violations), len(violations)
