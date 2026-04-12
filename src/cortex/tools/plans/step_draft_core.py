"""Parse and render step-by-step plan draft files (footer state + H2 sections)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from cortex.core.models import PlanSectionStatus

STEP_STATE_BEGIN = "<!-- CORTEX_STEP_PLAN_STATE\n"
STEP_STATE_CLOSE = "-->"

# AI: Order matches the plan authoring template used across Synapse prompts.
SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("goal", "Goal"),
    ("context", "Context"),
    ("implementation_steps", "Implementation Steps"),
    ("verification", "Verification"),
    ("testing", "Testing Strategy"),
)

CANONICAL_SECTION_KEYS: frozenset[str] = frozenset(k for k, _ in SECTION_ORDER)

_HEADING_TO_KEY: dict[str, str] = {}
for key, label in SECTION_ORDER:
    _HEADING_TO_KEY[label.lower()] = key

# AI: Plans in the wild use alternate H2 titles; map them to the same canonical keys.
_HEADING_TO_KEY["verification checklist"] = "verification"
_HEADING_TO_KEY["steps"] = "implementation_steps"
_HEADING_TO_KEY["implementation"] = "implementation_steps"


@dataclass(frozen=True, slots=True)
class StepSectionRecord:
    """Serialized step-plan section metadata (footer JSON)."""

    key: str
    status: PlanSectionStatus
    approved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ParsedStepDraft:
    """In-memory representation of a draft plan file."""

    frontmatter: str | None
    bodies: dict[str, str]
    records: tuple[StepSectionRecord, ...]


def draft_filename_for_slug(slug: str) -> str:
    """Return draft filename stem including ``draft-`` prefix."""
    base = slug.removeprefix("draft-")
    return f"draft-{base}.md"


def split_frontmatter(markdown: str) -> tuple[str | None, str]:
    """Split YAML frontmatter (if present) from the remainder."""
    if not markdown.startswith("---\n"):
        return (None, markdown)
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return (None, markdown)
    fm = markdown[: end + 5]
    rest = markdown[end + 5 :].lstrip("\n")
    return (fm, rest)


def _strip_step_footer(markdown: str) -> tuple[str, str | None]:
    idx = markdown.rfind(STEP_STATE_BEGIN)
    if idx == -1:
        return (markdown, None)
    head = markdown[:idx].rstrip()
    tail = markdown[idx:].rstrip("\n")
    if not tail.endswith(STEP_STATE_CLOSE):
        return (markdown, None)
    close_idx = tail.rfind(STEP_STATE_CLOSE)
    json_part = tail[len(STEP_STATE_BEGIN) : close_idx].strip()
    return (head, json_part)


def _record_from_dict(raw: dict[str, object]) -> StepSectionRecord:
    key = str(raw["key"])
    status = PlanSectionStatus(str(raw["status"]))
    approved_raw = raw.get("approved_at")
    approved_at: datetime | None = None
    if approved_raw:
        text = str(approved_raw)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        approved_at = datetime.fromisoformat(text)
    return StepSectionRecord(key=key, status=status, approved_at=approved_at)


def _parse_h2_sections(body: str) -> dict[str, str]:
    """Map canonical section keys to body text (trimmed), excluding headings."""
    lines = body.splitlines()
    current_key: str | None = None
    buf: list[str] = []
    out: dict[str, str] = {}

    def flush() -> None:
        nonlocal buf, current_key
        if current_key is not None:
            out[current_key] = "\n".join(buf).strip()
        buf = []

    heading_re = re.compile(r"^##\s+(.+)\s*$")
    for line in lines:
        m = heading_re.match(line)
        if m:
            flush()
            title = m.group(1).strip()
            current_key = _HEADING_TO_KEY.get(title.lower())
            if current_key is None:
                current_key = None
            buf = []
            continue
        if current_key is not None:
            buf.append(line)
    flush()
    return out


def parse_step_draft_file(text: str) -> ParsedStepDraft | None:
    """Parse a draft plan; returns None if footer state is missing or invalid."""
    head, json_payload = _strip_step_footer(text)
    if not json_payload:
        return None
    try:
        data = json.loads(json_payload)
    except json.JSONDecodeError:
        return None
    if data.get("version") != 1:
        return None
    raw_sections_obj = data.get("sections")
    if not isinstance(raw_sections_obj, list):
        return None
    raw_sections = cast(list[object], raw_sections_obj)
    records: list[StepSectionRecord] = []
    for item_raw in raw_sections:
        if not isinstance(item_raw, dict):
            return None
        item = cast(dict[str, object], item_raw)
        try:
            records.append(_record_from_dict(item))
        except (KeyError, ValueError, TypeError):
            return None
    fm, body = split_frontmatter(head)
    bodies = _parse_h2_sections(body)
    return ParsedStepDraft(
        frontmatter=fm,
        bodies=bodies,
        records=tuple(records),
    )


def initial_section_records() -> tuple[StepSectionRecord, ...]:
    """Default step graph: goal drafted first, others pending."""
    out: list[StepSectionRecord] = []
    for idx, (key, _label) in enumerate(SECTION_ORDER):
        if idx == 0:
            out.append(StepSectionRecord(key=key, status=PlanSectionStatus.DRAFT))
        else:
            out.append(StepSectionRecord(key=key, status=PlanSectionStatus.PENDING))
    return tuple(out)


def _records_to_json(records: tuple[StepSectionRecord, ...]) -> str:
    payload: list[dict[str, object]] = []
    for r in records:
        item: dict[str, object] = {
            "key": r.key,
            "status": r.status.value,
        }
        if r.approved_at is not None:
            item["approved_at"] = r.approved_at.astimezone(UTC).isoformat()
        payload.append(item)
    return json.dumps({"version": 1, "sections": payload}, separators=(",", ":"))


def render_published_plan(frontmatter: str | None, bodies: dict[str, str]) -> str:
    """Render final markdown without step-plan machine footer."""
    parts: list[str] = []
    if frontmatter:
        parts.append(frontmatter.rstrip("\n"))
        parts.append("")
    for key, label in SECTION_ORDER:
        body = bodies.get(key, "").strip()
        if not body:
            continue
        parts.append(f"## {label}")
        parts.append("")
        parts.append(body)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def canonical_section_key(raw: str) -> str | None:
    """Normalize user input to a canonical section key."""
    stripped = raw.strip()
    lowered = stripped.lower()
    if lowered in CANONICAL_SECTION_KEYS:
        return lowered
    return _HEADING_TO_KEY.get(lowered)


def render_step_draft_file(
    frontmatter: str | None,
    bodies: dict[str, str],
    records: tuple[StepSectionRecord, ...],
) -> str:
    """Serialize frontmatter, H2 bodies in canonical order, and footer state."""
    parts: list[str] = []
    if frontmatter:
        parts.append(frontmatter.rstrip("\n"))
        parts.append("")
    for key, label in SECTION_ORDER:
        body = bodies.get(key, "").strip()
        if body:
            parts.append(f"## {label}")
            parts.append("")
            parts.append(body)
            parts.append("")
    core = "\n".join(parts).rstrip() + "\n"
    footer = f"{STEP_STATE_BEGIN}{_records_to_json(records)}\n{STEP_STATE_CLOSE}\n"
    return core + footer


def extract_goal_markdown(full_markdown: str) -> str:
    """Return markdown body under ``## Goal`` (trimmed), excluding the heading."""
    fm, body = split_frontmatter(full_markdown)
    _ = fm
    bodies = _parse_h2_sections(body)
    return bodies.get("goal", "").strip()


def replace_section_body(
    bodies: dict[str, str], key: str, new_body: str
) -> dict[str, str]:
    """Return a shallow copy of *bodies* with *key* set to *new_body*."""
    merged = dict(bodies)
    merged[key] = new_body.strip()
    return merged


def find_next_pending_key(records: tuple[StepSectionRecord, ...]) -> str | None:
    """First section in canonical order whose status is ``pending``."""
    order_keys = [k for k, _ in SECTION_ORDER]
    status_by_key = {r.key: r.status for r in records}
    for key in order_keys:
        if status_by_key.get(key) == PlanSectionStatus.PENDING:
            return key
    return None


def find_draft_section_key(records: tuple[StepSectionRecord, ...]) -> str | None:
    """Section currently in ``draft`` status, if any."""
    for r in records:
        if r.status == PlanSectionStatus.DRAFT:
            return r.key
    return None


def update_record_status(
    records: tuple[StepSectionRecord, ...],
    key: str,
    *,
    status: PlanSectionStatus,
    approved_at: datetime | None,
) -> tuple[StepSectionRecord, ...]:
    """Return new records tuple with *key* updated."""
    out: list[StepSectionRecord] = []
    for r in records:
        if r.key == key:
            out.append(
                StepSectionRecord(key=key, status=status, approved_at=approved_at)
            )
        else:
            out.append(r)
    return tuple(out)


def all_sections_terminal(records: tuple[StepSectionRecord, ...]) -> bool:
    """True when every section is approved or skipped."""
    return all(
        r.status in (PlanSectionStatus.APPROVED, PlanSectionStatus.SKIPPED)
        for r in records
    )
