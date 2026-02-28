"""Roadmap corruption pattern detection logic."""

import re

from cortex.tools.roadmap_corruption_models import CorruptionMatch


def _detect_pattern1(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect pattern 1: missing space/newline after completion date followed by capital."""
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


def _detect_phase_truncation_patterns(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect truncation corruption in phase titles.

    Detects patterns like "Phase 54lizer Pattern" where the beginning of the title
    was lost (missing colon, lowercase+uppercase sequence indicates truncation).
    Pattern matches: "Phase" + digits + lowercase letters + (optional space) + uppercase
    letter (missing colon).
    """
    pattern = re.compile(
        r"\bPhase (\d+)([a-z]+)\s*([A-Z][a-zA-Z\s]*?)(?=\s*\*\*|\s*-|\s*$|$)"
    )
    for i, line in enumerate(lines, 1):
        for match in pattern.finditer(line):
            phase_num = match.group(1)
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed=f"Phase {phase_num}: [MANUAL FIX REQUIRED - check activeContext.md for correct title]",
                    pattern="phase_title_truncation",
                )
            )


def _detect_phase_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect corruption patterns related to Phase references."""
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
    _detect_phase_truncation_patterns(lines, matches)


def _detect_score_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect corruption patterns related to score formats."""
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


def _detect_plan24_percent_to(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect number/percent + 'to' -> 'X% to' (e.g. 89.89to -> 89.89% to)."""
    p_to = re.compile(r"(\d+\.?\d*)to\b")
    for i, line in enumerate(lines, 1):
        for m in p_to.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}% to",
                    pattern="percent_to_missing_space",
                )
            )


def _detect_plan24_number_actual(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect number + 'ctual' -> 'X actual' (e.g. 0ctual -> 0 actual)."""
    p_actual = re.compile(r"(\d+)ctual\b")
    for i, line in enumerate(lines, 1):
        for m in p_actual.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)} actual",
                    pattern="number_actual_missing_space",
                )
            )


def _detect_plan24_ceeds_percent(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect 'ceeds' + digits -> '(exceeds X%' (e.g. ceeds90 -> (exceeds 90%)."""
    p_ceeds = re.compile(r"ceeds(\d+)\b")
    for i, line in enumerate(lines, 1):
        for m in p_ceeds.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"(exceeds {m.group(1)}%",
                    pattern="exceeds_percent_corrupted",
                )
            )


def _detect_plan24_files_unchanged(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect number + 'es unchanged' -> 'X files unchanged'."""
    p_files = re.compile(r"(\d+)es\s+unchanged\b")
    for i, line in enumerate(lines, 1):
        for m in p_files.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)} files unchanged",
                    pattern="files_unchanged_corrupted",
                )
            )


def _detect_plan24_percent_coverage(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect number + 'coverage' -> 'X% coverage' (e.g. 90.32coverage)."""
    p_cov = re.compile(r"(\d+\.?\d*)coverage\b")
    for i, line in enumerate(lines, 1):
        for m in p_cov.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}% coverage",
                    pattern="percent_coverage_missing_space",
                )
            )


def _detect_plan24_malformed_date(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect 2026MM-DD + 'ixed' -> '2026-MM-DD) - Fixed'."""
    p_date = re.compile(r"2026(\d{2})-(\d{2})(ixed)\b")
    for i, line in enumerate(lines, 1):
        for m in p_date.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"2026-{m.group(1)}-{m.group(2)}) - Fixed",
                    pattern="malformed_date_fixed",
                )
            )


def _detect_plan24_phrase_patterns(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect Phase 24 phrase corruptions: percent+to, number+ctual, ceeds, etc."""
    _detect_plan24_percent_to(lines, matches)
    _detect_plan24_number_actual(lines, matches)
    _detect_plan24_ceeds_percent(lines, matches)
    _detect_plan24_files_unchanged(lines, matches)
    _detect_plan24_percent_coverage(lines, matches)
    _detect_plan24_malformed_date(lines, matches)


def _detect_misc_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect miscellaneous corruption patterns."""
    _detect_pattern3_implemented(lines, matches)
    _detect_pattern8_and_9(lines, matches)
    _detect_plan24_phrase_patterns(lines, matches)


def _detect_phrase_corruption(content: str) -> list[CorruptionMatch]:
    """Detect only generic phrase corruptions (percent_to, percent_coverage, etc.).

    Safe for progress.md and other memory-bank files that share phrase patterns
    with roadmap but not roadmap-specific patterns (completion date, phase links).
    Also includes truncation detection for phase titles.
    """
    matches: list[CorruptionMatch] = []
    lines = content.split("\n")
    _detect_plan24_phrase_patterns(lines, matches)
    _detect_phase_truncation_patterns(lines, matches)
    return matches


def _detect_roadmap_corruption(content: str) -> list[CorruptionMatch]:
    """Detect all corruption patterns in roadmap content."""
    matches: list[CorruptionMatch] = []
    lines = content.split("\n")
    _detect_completion_date_patterns(lines, matches)
    _detect_phase_patterns(lines, matches)
    _detect_score_patterns(lines, matches)
    _detect_misc_patterns(lines, matches)
    return matches


def detect_roadmap_corruption(content: str) -> list[CorruptionMatch]:
    """Public wrapper for roadmap corruption detection."""
    return _detect_roadmap_corruption(content)


def detect_phrase_corruption(content: str) -> list[CorruptionMatch]:
    """Public wrapper for phrase-only corruption detection (progress.md safe)."""
    return _detect_phrase_corruption(content)
