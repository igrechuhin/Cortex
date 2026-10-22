"""Helpers for plan roadmap registration: parsing, I/O, result builders."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass

from cortex.core.constants import MemoryBankFile
from cortex.core.models import PlanStatus
from cortex.core.plan_metadata import resolve_plan_status_token
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.plans.entries_content import extract_plan_path_from_bullet
from cortex.tools.plans.register_models import RegisterPlanResult
from cortex.validation.roadmap_models import KEY_TO_SECTION, SECTION_TO_KEY

logger = logging.getLogger(__name__)

_REFERENCE_HEADINGS: frozenset[str] = frozenset(
    (
        "Investigation Plans (Archive / Reference)",
        "Recent Findings",
        "Completed Milestones",
        "Planned Phases",
    )
)


def parse_roadmap_sections(content: str) -> dict[str, tuple[int, int]]:
    """Parse roadmap to get section boundaries.

    Returns: {section_id: (start_line, end_line)}
    """
    sections: dict[str, tuple[int, int]] = {}
    lines = content.split("\n")
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$")
    header_to_section = SECTION_TO_KEY

    current_section_name: str | None = None
    current_section_start = 0

    for i, line in _registration_lines(lines):
        match = header_pattern.match(line)
        if not match:
            continue
        header_text = match.group(2)
        section_id = header_to_section.get(header_text)

        if current_section_name is not None:
            sections[current_section_name] = (current_section_start, i - 1)
            current_section_name = None

        if section_id:
            current_section_name = section_id
            current_section_start = i

    if current_section_name is not None:
        sections[current_section_name] = (current_section_start, len(lines) - 1)

    return sections


def find_insertion_line_for_section(
    lines: list[str],
    section_start: int,
    section_end: int,
    position: str = "last",
) -> int:
    """Find the line number where a new entry should be inserted."""
    first_bullet = -1
    last_bullet = -1

    for i, line in _registration_lines(lines):
        if i > section_end:
            break
        if i > section_start and line.startswith("- "):
            if first_bullet == -1:
                first_bullet = i
            last_bullet = i

    if position == "first":
        if first_bullet != -1:
            return first_bullet
        return section_start + 1

    if last_bullet != -1:
        return last_bullet + 1
    return section_start + 1


def _normalize_extracted_plan_path(path: str) -> str:
    normalized = path.strip().strip("`").rstrip(".,)")
    normalized = normalized.lstrip("./")
    if normalized.startswith("cortex/plans/"):
        normalized = normalized[len("cortex/") :]
    if normalized.startswith("plans/"):
        return f".cortex/{normalized}"
    if normalized.startswith(".cortex/plans/"):
        return normalized
    return normalized


def _normalize_plan_path(plan_ref: str) -> str:
    normalized = _normalize_extracted_plan_path(plan_ref)
    if normalized.startswith(".cortex/plans/"):
        return normalized
    return f".cortex/plans/{normalized}"


def _append_plan_path(
    description: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
) -> str:
    plan_ref = plan_relative_path or plan_file_name
    if plan_ref is None:
        return description
    normalized = _normalize_plan_path(plan_ref)
    labels = re.findall(r"Plan:\s*([^\s]+)", description)
    if labels and _normalize_extracted_plan_path(labels[-1]) == normalized:
        return description
    return f"{description.rstrip().rstrip('.')}. Plan: {normalized}"


def _build_entry_text(
    plan_title: str,
    status: str,
    description: str,
    *,
    plan_file_name: str | None,
    plan_relative_path: str | None,
) -> str:
    rendered = _append_plan_path(description, plan_file_name, plan_relative_path)
    return f"- **{plan_title}** - {status} - {rendered}"


def _registration_plan_path(line: str) -> str | None:
    """Recognize registration rows, not incidental paths in prose."""
    if not re.match(
        r"^-\s+(?:\*\*.+?\*\*\s+[—–-]\s+[^\n]+?\s+[—–-]\s+|"
        + r"\[[ xX]\]\s+|Plan:\s*)",
        line,
    ):
        return None
    return extract_plan_path_from_bullet(line)


def _registration_lines(lines: list[str]) -> Iterator[tuple[int, str]]:
    """Ignore fenced examples and the established archive/reference section."""
    fence: str | None = None
    reference_level: int | None = None
    for index, line in enumerate(lines):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is not None:
            if (
                marker
                and marker.group(1)[0] == fence[0]
                and len(marker.group(1)) >= len(fence)
                and not marker.group(2).strip()
            ):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            if reference_level is not None and level <= reference_level:
                reference_level = None
            if heading.group(2) in _REFERENCE_HEADINGS:
                reference_level = (
                    min(reference_level, level) if reference_level else level
                )
        if reference_level is None:
            yield index, line


def _find_existing_plan_line(
    lines: list[str], plan_path: str | None, entry_text: str
) -> int | None:
    matches = [
        i
        for i, line in _registration_lines(lines)
        if (plan_path is not None and _registration_plan_path(line) == plan_path)
        or (plan_path is None and line.strip() == entry_text.strip())
    ]
    if len(matches) > 1:
        raise ValueError(f"Multiple canonical roadmap registrations for {plan_path}")
    return matches[0] if matches else None


def _ensure_section_exists(
    content: str,
    sections: dict[str, tuple[int, int]],
    section_id: str,
) -> tuple[str, dict[str, tuple[int, int]]]:
    if section_id in sections:
        return content, sections

    header = KEY_TO_SECTION.get(section_id)
    if not header:
        return content, sections

    logger.warning("Section '%s' not found in roadmap, creating it.", header)
    content = content.rstrip("\n") + f"\n\n## {header}\n\n"
    sections = parse_roadmap_sections(content)
    return content, sections


def _insert_entry_in_section(
    lines: list[str],
    section_start: int,
    section_end: int,
    entry_text: str,
    position: str,
) -> tuple[str, int | None]:
    """Insert only after the global identity lookup has found no existing row."""
    insert_line = find_insertion_line_for_section(
        lines=lines,
        section_start=section_start,
        section_end=section_end,
        position=position,
    )
    lines.insert(insert_line, entry_text)
    return ("\n".join(lines), insert_line + 1)


@dataclass(frozen=True, slots=True)
class _ResolvedSection:
    content: str
    start: int
    end: int


def _resolve_section(content: str, section_id: str) -> _ResolvedSection | None:
    """Return resolved section bounds after ensuring section exists, or None."""
    sections = parse_roadmap_sections(content)
    content, sections = _ensure_section_exists(content, sections, section_id)
    if section_id not in sections:
        return None
    start, end = sections[section_id]
    return _ResolvedSection(content=content, start=start, end=end)


def register_plan_entry(
    content: str,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
    position: str = "last",
    plan_file_name: str | None = None,
    plan_relative_path: str | None = None,
) -> tuple[str, int | None]:
    """Register a plan entry in the roadmap."""
    lines = content.split("\n")
    entry_text = _build_entry_text(
        plan_title,
        status,
        description,
        plan_file_name=plan_file_name,
        plan_relative_path=plan_relative_path,
    )
    plan_ref = plan_relative_path or plan_file_name
    plan_path = (
        _normalize_plan_path(plan_ref)
        if plan_ref
        else _registration_plan_path(entry_text)
    )
    existing = _find_existing_plan_line(lines, plan_path, entry_text)
    if existing is not None:
        lines[existing] = entry_text + ("\r" if lines[existing].endswith("\r") else "")
        return "\n".join(lines), existing + 1
    return _insert_registered_entry(content, section_id, entry_text, position)


def _insert_registered_entry(
    content: str, section_id: str, entry_text: str, position: str
) -> tuple[str, int | None]:
    resolved = _resolve_section(content, section_id)
    if resolved is None:
        return content, None
    return _insert_entry_in_section(
        lines=resolved.content.split("\n"),
        section_start=resolved.start,
        section_end=resolved.end,
        entry_text=entry_text + ("\r" if "\r\n" in resolved.content else ""),
        position=position,
    )


def is_completed_status(status: str) -> bool:
    """Return True if status indicates completed work (not allowed in roadmap)."""
    return resolve_plan_status_token(status) == PlanStatus.DONE


@dataclass(frozen=True, slots=True)
class SectionValidation:
    section_id: str | None
    error_message: str | None


def validate_registration_section(section: str) -> SectionValidation:
    """Validate section identifier."""
    section_map = {
        "blockers": "blockers",
        "active_work": "active_work",
        "future": "future",
        "pending": "pending",
    }

    section_id = section_map.get(section.lower())
    if not section_id:
        return SectionValidation(
            section_id=None,
            error_message=f"Section must be one of: {', '.join(section_map.keys())}",
        )
    return SectionValidation(section_id=section_id, error_message=None)


def create_register_error_result(error: str) -> RegisterPlanResult:
    """Create an error result for plan registration."""
    return RegisterPlanResult(
        status=ToolResultStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="Failed to register plan",
        line_inserted=None,
        section=None,
        error=error,
        parallel_steps_count=None,
        sequential_steps_count=None,
    )


def create_register_success_result(
    section_id: str,
    line_inserted: int,
    *,
    parallel_steps_count: int | None = None,
    sequential_steps_count: int | None = None,
) -> RegisterPlanResult:
    """Create a result; section denotes the requested insertion destination."""
    return RegisterPlanResult(
        status=ToolResultStatus.SUCCESS,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Plan registered at line {line_inserted}",
        line_inserted=line_inserted,
        section=section_id,
        error=None,
        parallel_steps_count=parallel_steps_count,
        sequential_steps_count=sequential_steps_count,
    )
