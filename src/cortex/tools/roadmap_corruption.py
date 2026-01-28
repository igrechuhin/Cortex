"""
Roadmap corruption fixing tools.

This module contains MCP tools for detecting and fixing text corruption
patterns in the Memory Bank `roadmap.md` file.
"""

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.managers.initialization import get_project_root
from cortex.server import mcp


class CorruptionMatch(BaseModel):
    """A detected corruption match."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    line_num: int = Field(ge=1, description="Line number")
    original: str = Field(description="Original corrupted text")
    fixed: str = Field(description="Fixed text")
    pattern: str = Field(description="Pattern that matched")


class FixRoadmapCorruptionResult(BaseModel):
    """Result of roadmap corruption fixing operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(description="Whether operation succeeded")
    file_name: str = Field(description="File name")
    corruption_count: int = Field(ge=0, description="Number of corruptions found")
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch](),
        description="List of fixes applied",
    )
    error_message: str | None = Field(default=None, description="Error message if any")


def _detect_pattern1(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect pattern 1: missing space/newline after completion date
    followed by capital."""
    pattern = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})([A-Za-z])")
    for i, line in enumerate(lines, 1):
        for m in pattern.finditer(line):
            if m.group(3).isupper():
                matches.append(
                    CorruptionMatch(
                        line_num=i,
                        original=m.group(0),
                        fixed=f"{m.group(1)} {m.group(2)}\n- [Phase",
                        pattern="missing_space_newline_after_completion_date",
                    )
                )


def _detect_pattern6_and_7(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect patterns 6 and 7: missing newline before phase links."""
    p6 = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})( - \[Phase)")
    for i, line in enumerate(lines, 1):
        for m in p6.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)} {m.group(2)}\n{m.group(3)}",
                    pattern="missing_newline_before_phase_link",
                )
            )
    p7 = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})(Phase)")
    for i, line in enumerate(lines, 1):
        for m in p7.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)} {m.group(2)}\n- [{m.group(3)}",
                    pattern="missing_space_newline_before_phase",
                )
            )


def _detect_completion_date_primary(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect primary completion date patterns (1, 6, 7)."""
    _detect_pattern1(lines, matches)
    _detect_pattern6_and_7(lines, matches)


def _detect_completion_date_secondary(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect secondary completion date patterns (10, 11)."""
    p10 = re.compile(r"(Target completion: \d{4}-\d{2}-\d{2}) (\[Conditional)")
    for i, line in enumerate(lines, 1):
        for m in p10.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}\n- {m.group(2)}",
                    pattern="missing_newline_before_conditional",
                )
            )
    p11 = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})([^ -])")
    for i, line in enumerate(lines, 1):
        for m in p11.finditer(line):
            already_added = any(
                existing.line_num == i and existing.original == m.group(0)
                for existing in matches
            )
            if not already_added:
                matches.append(
                    CorruptionMatch(
                        line_num=i,
                        original=m.group(0),
                        fixed=f"{m.group(1)} {m.group(2)}{m.group(3)}",
                        pattern="missing_space_after_completion_colon",
                    )
                )


def _detect_completion_date_patterns(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect all 'Target completion:' date corruption patterns."""
    _detect_completion_date_primary(lines, matches)
    _detect_completion_date_secondary(lines, matches)


def _detect_phase_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect corruption patterns related to Phase references."""
    # Pattern 2: "Phase X% rate" -> "Phase X: Validate"
    pattern2 = re.compile(r"Phase (\d+)% rate")
    for i, line in enumerate(lines, 1):
        for match in pattern2.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed=f"Phase {match.group(1)}: Validate",
                    pattern="corrupted_phase_number",
                )
            )
    # Pattern 4: Missing newline before "-Phase"
    pattern4 = re.compile(r"([^\n])-Phase (\d+)")
    for i, line in enumerate(lines, 1):
        for match in pattern4.finditer(line):
            before = match.group(1)
            phase_num = match.group(2)
            fixed = (
                f"{before}\n- [Phase {phase_num}"
                if before.strip().endswith(")")
                else f"{before} - [Phase {phase_num}"
            )
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed=fixed,
                    pattern="missing_newline_before_phase",
                )
            )


def _detect_score_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect corruption patterns related to score formats."""
    # Pattern 5: "X.710 to Y.Z+" -> "X.7/10 to Y.Z+/10"
    pattern5 = re.compile(r"(\d+)\.(\d)(\d+) to (\d+)\.(\d+)\+")
    for i, line in enumerate(lines, 1):
        for match in pattern5.finditer(line):
            if match.group(3) == "10":
                matches.append(
                    CorruptionMatch(
                        line_num=i,
                        original=match.group(0),
                        fixed=(
                            f"{match.group(1)}.{match.group(2)}/10 to "
                            f"{match.group(4)}.{match.group(5)}+/10"
                        ),
                        pattern="corrupted_score_format",
                    )
                )
    # Pattern 12: "8.710" -> "8.7/10" standalone
    pattern12 = re.compile(r"(\d+)\.(\d)(10)(\s|$)")
    for i, line in enumerate(lines, 1):
        for match in pattern12.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed=f"{match.group(1)}.{match.group(2)}/10{match.group(4)}",
                    pattern="corrupted_standalone_score",
                )
            )


def _detect_pattern3_implemented(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect pattern 3: corrupted 'Implemented' text."""
    pattern = re.compile(r"\bented\b")
    for i, line in enumerate(lines, 1):
        for match in pattern.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed="Implemented",
                    pattern="corrupted_implemented",
                )
            )


def _detect_pattern8_and_9(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect patterns 8 and 9: date-fix and archive path issues."""
    p8 = re.compile(r"(\d{4}-\d{2}-\d{2})(Fix)")
    for i, line in enumerate(lines, 1):
        for m in p8.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}) - {m.group(2)}",
                    pattern="missing_paren_space_before_fix",
                )
            )
    p9 = re.compile(r"(archive/Phase \d+)(phase-\d+)")
    for i, line in enumerate(lines, 1):
        for m in p9.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}/{m.group(2)}",
                    pattern="missing_slash_in_archive_path",
                )
            )


def _detect_misc_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect miscellaneous corruption patterns."""
    _detect_pattern3_implemented(lines, matches)
    _detect_pattern8_and_9(lines, matches)


def _detect_roadmap_corruption(content: str) -> list[CorruptionMatch]:
    """Detect all corruption patterns in roadmap content."""
    matches: list[CorruptionMatch] = []
    lines = content.split("\n")
    _detect_completion_date_patterns(lines, matches)
    _detect_phase_patterns(lines, matches)
    _detect_score_patterns(lines, matches)
    _detect_misc_patterns(lines, matches)
    return matches


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

    # Sort matches by line number (descending) to avoid offset issues
    matches_sorted = sorted(matches, key=lambda m: m.line_num, reverse=True)

    lines = content.split("\n")
    for match in matches_sorted:
        line_idx = match.line_num - 1
        if line_idx < len(lines):
            line = lines[line_idx]
            # Replace the corrupted pattern
            if "\n" in match.fixed:
                # Handle newline insertion - split the fix
                parts = match.fixed.split("\n", 1)
                lines[line_idx] = line.replace(match.original, parts[0])
                if len(parts) > 1 and line_idx + 1 < len(lines):
                    # Insert new line or prepend to next line
                    if parts[1].startswith("- "):
                        lines.insert(line_idx + 1, parts[1])
                    else:
                        lines[line_idx + 1] = parts[1] + lines[line_idx + 1]
            else:
                lines[line_idx] = line.replace(match.original, match.fixed)

    return "\n".join(lines)


def _create_roadmap_error_response(error_msg: str) -> str:
    """Create error response for roadmap corruption."""
    result = FixRoadmapCorruptionResult(
        success=False,
        file_name="roadmap.md",
        corruption_count=0,
        fixes_applied=[],
        error_message=error_msg,
    )
    return json.dumps(result.model_dump(), indent=2)


def _create_roadmap_success_response(matches: list[CorruptionMatch]) -> str:
    """Create success response for roadmap corruption."""
    result = FixRoadmapCorruptionResult(
        success=True,
        file_name="roadmap.md",
        corruption_count=len(matches),
        fixes_applied=matches,
        error_message=None,
    )
    return json.dumps(result.model_dump(), indent=2)


@mcp.tool()
async def fix_roadmap_corruption(
    project_root: str | None = None, dry_run: bool = False
) -> str:
    """Fix text corruption in roadmap.md file.

    Detects and fixes corruption patterns: missing spaces/newlines, corrupted
    text like 'ented'->'Implemented', malformed dates, corrupted scores.
    """
    try:
        root_path = Path(get_project_root(project_root))
        roadmap_path = root_path / ".cortex" / "memory-bank" / "roadmap.md"
        if not roadmap_path.exists():
            return _create_roadmap_error_response(
                f"roadmap.md not found at {roadmap_path}"
            )
        content = roadmap_path.read_text(encoding="utf-8")
        matches = _detect_roadmap_corruption(content)
        if not dry_run and matches:
            fixed_content = _apply_roadmap_fixes(content, matches)
            _ = roadmap_path.write_text(fixed_content, encoding="utf-8")
        return _create_roadmap_success_response(matches)
    except Exception as e:
        return _create_roadmap_error_response(str(e))
