"""Helpers for plan roadmap registration: parsing, I/O, result builders."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from cortex.core.constants import MemoryBankFile
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.plans.register_models import RegisterPlanResult
from cortex.validation.roadmap_models import KEY_TO_SECTION, SECTION_TO_KEY

logger = logging.getLogger(__name__)


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

    for i, line in enumerate(lines):
        match = header_pattern.match(line)
        if not match:
            continue
        header_text = match.group(2)
        section_id = header_to_section.get(header_text)

        if current_section_name is not None:
            sections[current_section_name] = (current_section_start, i - 1)

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

    for i in range(section_start + 1, section_end + 1):
        if lines[i].startswith("- "):
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


def extract_plan_path_from_bullet(line: str) -> str | None:
    """Extract and normalize a plan path from roadmap bullet text."""
    plan_label_match = re.search(r"Plan:\s*([^\s]+)", line)
    if plan_label_match:
        return _normalize_extracted_plan_path(plan_label_match.group(1))

    plan_path_match = re.search(r"`?((?:\.cortex/)?plans/[^\s`]+?\.md)`?", line)
    if plan_path_match:
        return _normalize_extracted_plan_path(plan_path_match.group(1))
    return None


def _normalize_plan_path(plan_ref: str) -> str:
    raw = plan_ref.strip()
    if raw.startswith(".cortex/plans/"):
        return raw
    return f".cortex/plans/{raw}"


def _append_plan_path(
    description: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
) -> str:
    plan_ref = plan_relative_path or plan_file_name
    if plan_ref is None:
        return description
    if extract_plan_path_from_bullet(description) is not None:
        return description
    normalized = _normalize_plan_path(plan_ref)
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


def _find_existing_plan_line(
    lines: list[str],
    section_start: int,
    section_end: int,
    plan_path: str | None,
    entry_text: str,
) -> int | None:
    if plan_path:
        for i in range(section_start + 1, section_end + 1):
            if i < len(lines):
                existing_plan_path = extract_plan_path_from_bullet(lines[i])
                if existing_plan_path and plan_path == existing_plan_path:
                    return i

    section_content = "\n".join(lines[section_start : section_end + 1])
    if entry_text.strip() in section_content:
        return section_start

    return None


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
    plan_path = extract_plan_path_from_bullet(entry_text)
    existing_line = _find_existing_plan_line(
        lines=lines,
        section_start=section_start,
        section_end=section_end,
        plan_path=plan_path,
        entry_text=entry_text,
    )
    if existing_line is not None:
        return ("\n".join(lines), None)
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
    resolved = _resolve_section(content, section_id)
    if resolved is None:
        return (content, None)
    content = resolved.content
    entry_text = _build_entry_text(
        plan_title,
        status,
        description,
        plan_file_name=plan_file_name,
        plan_relative_path=plan_relative_path,
    )
    updated_content, inserted_line = _insert_entry_in_section(
        lines=content.split("\n"),
        section_start=resolved.start,
        section_end=resolved.end,
        entry_text=entry_text,
        position=position,
    )
    if inserted_line is None:
        return (content, None)
    return (updated_content, inserted_line)


def is_completed_status(status: str) -> bool:
    """Return True if status indicates completed work (not allowed in roadmap)."""
    normalized = status.strip().upper()
    return normalized in ("COMPLETED", "COMPLETE", "DONE")


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
    """Create a success result for plan registration."""
    return RegisterPlanResult(
        status=ToolResultStatus.SUCCESS,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Plan registered in '{section_id}' section at line {line_inserted}",
        line_inserted=line_inserted,
        section=section_id,
        error=None,
        parallel_steps_count=parallel_steps_count,
        sequential_steps_count=sequential_steps_count,
    )
