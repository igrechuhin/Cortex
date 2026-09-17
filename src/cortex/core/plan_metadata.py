"""Scoped parsing for plan frontmatter and supported legacy metadata lines."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from cortex.core.models._enums import PlanExecutionMode, PlanStatus
from cortex.core.pydantic_extra import EXTRA_FORBID

_FIELD_RE_TEMPLATE = r"^{field}[ \t]*:[ \t]*(.*)$"
_LEGACY_STATUS_RE = re.compile(
    r"^\*\*Status\*\*\s*:\s*([^\n.]+)", re.IGNORECASE | re.MULTILINE
)
_STATUS_ALIASES: dict[str, PlanStatus] = {
    "COMPLETE": PlanStatus.DONE,
    "COMPLETED": PlanStatus.DONE,
}


class PlanStatusMetadata(BaseModel):
    """Canonical status plus the source token and recognition result."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    status: PlanStatus = PlanStatus.PENDING
    raw_token: str | None = None
    recognized: bool = False
    conflicting: bool = False


def first_frontmatter_block(content: str) -> str | None:
    """Return the first YAML frontmatter body when it is well formed."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return None


def _parse_scalar(raw: str) -> str:
    value = raw.strip()
    if value[:1] in {'"', "'"}:
        closing = _quoted_scalar_end(value)
        if closing is None:
            return value
        tail = value[closing + 1 :].strip()
        if tail and not tail.startswith("#"):
            return value
        return value[1:closing].replace(value[0] * 2, value[0]).strip()
    comment = value.find(" #")
    return value[:comment].strip() if comment >= 0 else value


def _quoted_scalar_end(value: str) -> int | None:
    quote = value[0]
    index = 1
    while index < len(value):
        if value[index] != quote:
            index += 1
            continue
        if quote == "'" and value[index : index + 2] == "''":
            index += 2
            continue
        if quote == '"' and value[index - 1] == "\\":
            index += 1
            continue
        return index
    return None


def read_frontmatter_fields(content: str, field: str) -> list[str]:
    """Read every scalar occurrence from the first frontmatter block."""
    block = first_frontmatter_block(content)
    if block is None:
        return []
    pattern = re.compile(
        _FIELD_RE_TEMPLATE.format(field=re.escape(field)), re.IGNORECASE | re.MULTILINE
    )
    return [_parse_scalar(match.group(1)) for match in pattern.finditer(block)]


def read_frontmatter_field(content: str, field: str) -> str | None:
    """Read the first scalar occurrence from the first frontmatter block."""
    values = read_frontmatter_fields(content, field)
    return values[0] if values else None


def resolve_plan_status_token(raw: str) -> PlanStatus | None:
    """Return the canonical status for a raw metadata token, or None."""
    token = raw.strip().upper().replace("-", "_").replace(" ", "_")
    for candidate in PlanStatus:
        if candidate.value == token:
            return candidate
    exact_alias = _STATUS_ALIASES.get(token)
    if exact_alias is not None:
        return exact_alias
    if re.fullmatch(r"COMPLETED?_\((?:\d{2}|\d{4})(?:[-_]\d{2}){2,5}\)", token):
        return PlanStatus.DONE
    return None


def read_plan_status_metadata(content: str) -> PlanStatusMetadata:
    """Read frontmatter status, with an explicit legacy heading fallback."""
    raw_values = read_frontmatter_fields(content, "status")
    if not raw_values:
        legacy = _LEGACY_STATUS_RE.search(_legacy_metadata_preamble(content))
        raw_values = [legacy.group(1).strip()] if legacy is not None else []
    canonical = [resolve_plan_status_token(raw) for raw in raw_values]
    recognized_values = {value for value in canonical if value is not None}
    conflicting = len(recognized_values) > 1 or (
        bool(recognized_values) and any(value is None for value in canonical)
    )
    selected = next(iter(recognized_values)) if len(recognized_values) == 1 else None
    return PlanStatusMetadata(
        status=selected or PlanStatus.PENDING,
        raw_token=" | ".join(raw_values) if raw_values else None,
        recognized=selected is not None and not conflicting,
        conflicting=conflicting,
    )


def _legacy_metadata_preamble(content: str) -> str:
    """Limit legacy status lookup to the unfenced document header."""
    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("```")
            or stripped.startswith("~~~")
            or stripped.startswith("## ")
        ):
            break
        lines.append(line)
    return "\n".join(lines)


def read_plan_execution(content: str) -> PlanExecutionMode:
    """Read canonical execution mode from frontmatter, defaulting to agent."""
    raw = read_frontmatter_field(content, "execution")
    if raw is None:
        return PlanExecutionMode.AGENT
    token = raw.strip().strip("\"'").lower()
    for candidate in PlanExecutionMode:
        if candidate.value == token:
            return candidate
    return PlanExecutionMode.AGENT
