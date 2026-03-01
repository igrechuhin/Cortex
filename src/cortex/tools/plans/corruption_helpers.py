"""Roadmap corruption fix and response helpers."""

import json
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.corruption_detectors import (
    detect_phrase_corruption,
    detect_roadmap_corruption,
)
from cortex.tools.plans.corruption_models import (
    CorruptionMatch,
    FixRoadmapCorruptionResult,
)


def fix_roadmap_content_if_needed(content: str) -> str:
    """Return content with corruption patterns fixed; use before writing roadmap.md.

    Use when writing roadmap.md via manage_file to prevent persisting corruption.
    """
    matches = detect_roadmap_corruption(content)
    return _apply_roadmap_fixes(content, matches) if matches else content


def fix_memory_bank_content_if_needed(content: str, file_name: str) -> str:
    """Return content with corruption patterns fixed for the given memory-bank file.

    - roadmap.md: full roadmap corruption fix (completion dates, phases, phrases).
    - progress.md: phrase-only fix (percent_to, percent_coverage, etc.) to avoid
      applying roadmap-specific patterns to progress.
    - Other files: returned unchanged.

    Plan files (.cortex/plans/*.md) are not written through manage_file; phrase
    corruption fix for plans is out of scope (rely on MD037 rule and
    verify-code-symbols guidance in memory-bank-workflow and agents).
    """
    if file_name == MemoryBankFile.ROADMAP:
        return fix_roadmap_content_if_needed(content)
    if file_name == MemoryBankFile.PROGRESS:
        matches = detect_phrase_corruption(content)
        return _apply_roadmap_fixes(content, matches) if matches else content
    return content


def _apply_roadmap_fixes(content: str, matches: list[CorruptionMatch]) -> str:
    """Apply fixes to roadmap content.

    Args:
        content: Original content
        matches: List of corruption matches to fix

    Returns:
        Fixed content
    """
    if not matches:
        return content

    matches_sorted = sorted(matches, key=lambda m: m.line_num, reverse=True)
    lines = content.split("\n")
    for match in matches_sorted:
        line_idx = match.line_num - 1
        if line_idx < len(lines):
            line = lines[line_idx]
            if "\n" in match.fixed:
                parts = match.fixed.split("\n", 1)
                lines[line_idx] = line.replace(match.original, parts[0])
                if len(parts) > 1 and line_idx + 1 < len(lines):
                    if parts[1].startswith("- "):
                        lines.insert(line_idx + 1, parts[1])
                    else:
                        lines[line_idx + 1] = parts[1] + lines[line_idx + 1]
            else:
                lines[line_idx] = line.replace(match.original, match.fixed)

    return "\n".join(lines)


def create_roadmap_error_response(error_msg: str) -> str:
    """Create error response for roadmap corruption."""
    result = FixRoadmapCorruptionResult(
        success=False,
        file_name=MemoryBankFile.ROADMAP,
        corruption_count=0,
        fixes_applied=[],
        error_message=error_msg,
    )
    return json.dumps(result.model_dump(), indent=2)


def _create_roadmap_success_response(matches: list[CorruptionMatch]) -> str:
    """Create success response for roadmap corruption."""
    result = FixRoadmapCorruptionResult(
        success=True,
        file_name=MemoryBankFile.ROADMAP,
        corruption_count=len(matches),
        fixes_applied=matches,
        error_message=None,
    )
    return json.dumps(result.model_dump(), indent=2)


def fix_roadmap_corruption_run(root_path: Path, dry_run: bool) -> tuple[str, bool]:
    """Run roadmap fix: path check, read, detect, apply. Return (response, ok)."""
    memory_bank_root = get_cortex_path(root_path, CortexResourceType.MEMORY_BANK)
    roadmap_path = memory_bank_root / MemoryBankFile.ROADMAP
    if not roadmap_path.exists():
        return (
            create_roadmap_error_response(
                f"{MemoryBankFile.ROADMAP} not found at {roadmap_path}"
            ),
            False,
        )
    content = roadmap_path.read_text(encoding="utf-8")
    matches = detect_roadmap_corruption(content)
    if not dry_run and matches:
        fixed_content = _apply_roadmap_fixes(content, matches)
        _ = roadmap_path.write_text(fixed_content, encoding="utf-8")
    return (_create_roadmap_success_response(matches), True)
