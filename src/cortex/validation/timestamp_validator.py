"""Timestamp validation utilities for Memory Bank files.

This module provides functions to validate timestamp formats in Memory Bank files.
All timestamps must use YYYY-MM-DD date-only format (no time components).
"""

import json
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _check_valid_date_patterns(
    line: str, line_num: int, date_pattern: str
) -> tuple[int, list[dict[str, object]]]:
    """Check for valid YYYY-MM-DD date-only format timestamps.

    Returns:
        Tuple of (valid_count, violations)
    """
    valid_count = 0
    violations: list[dict[str, object]] = []
    date_matches = re.finditer(date_pattern, line)
    for match in date_matches:
        date_str = match.group(1)
        if re.search(rf"{re.escape(date_str)}T\d", line):
            continue
        try:
            _ = datetime.strptime(date_str, "%Y-%m-%d")
            valid_count += 1
        except ValueError:
            pass
    return valid_count, violations


def _check_invalid_datetime_patterns(
    line: str, line_num: int, datetime_pattern: str
) -> tuple[int, list[dict[str, object]]]:
    """Check for datetime patterns with time component (YYYY-MM-DDTHH:MM).

    These are invalid as timestamps must be date-only (YYYY-MM-DD).

    Returns:
        Tuple of (invalid_count, violations)
    """
    invalid_format_count = 0
    violations: list[dict[str, object]] = []
    datetime_matches = re.finditer(datetime_pattern, line)
    for match in datetime_matches:
        timestamp_str = match.group(0)
        try:
            _ = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M")
            invalid_format_count += 1
            violations.append(
                {
                    "line": line_num,
                    "content": line.strip()[:80],
                    "timestamp": timestamp_str,
                    "issue": "Contains time component (should be YYYY-MM-DD date-only)",
                }
            )
        except ValueError:
            pass
    return invalid_format_count, violations


def _get_invalid_datetime_patterns() -> list[tuple[str, str]]:
    """Get patterns for invalid datetime formats with time components.

    Returns:
        List of (pattern, issue_message) tuples
    """
    return [
        (
            r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\b",
            "Contains time component (should be YYYY-MM-DD date-only)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\b",
            "Contains time component (should be YYYY-MM-DD date-only)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[Z+-]\d{2}:\d{2}\b",
            "Contains time component (should be YYYY-MM-DD date-only)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\b",
            "Contains time component (should be YYYY-MM-DD date-only)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\b",
            "Contains time component (should be YYYY-MM-DD date-only)",
        ),
    ]


def _add_pattern_violations(
    line: str,
    line_num: int,
    pattern: str,
    issue_msg: str,
    violations: list[dict[str, object]],
) -> int:
    """Add violations for a pattern match.

    Returns:
        Count of violations added
    """
    count = 0
    for match in re.finditer(pattern, line):
        count += 1
        violations.append(
            {
                "line": line_num,
                "content": line.strip()[:80],
                "timestamp": match.group(0),
                "issue": issue_msg,
            }
        )
    return count


def _check_invalid_datetime_formats(
    line: str, line_num: int
) -> tuple[int, list[dict[str, object]]]:
    """Check for invalid datetime formats (wrong separator, seconds, timezone, etc.).

    Returns:
        Tuple of (invalid_count, violations)
    """
    invalid_format_count = 0
    violations: list[dict[str, object]] = []
    patterns = _get_invalid_datetime_patterns()
    for pattern, issue_msg in patterns:
        count = _add_pattern_violations(line, line_num, pattern, issue_msg, violations)
        invalid_format_count += count
    return invalid_format_count, violations


def _check_other_date_formats(
    line: str, line_num: int, other_date_pattern: str
) -> tuple[int, list[dict[str, object]]]:
    """Check for other non-standard date formats (not YYYY-MM-DD).

    Returns:
        Tuple of (invalid_count, violations)
    """
    invalid_format_count = 0
    violations: list[dict[str, object]] = []
    other_matches = re.finditer(other_date_pattern, line)
    for match in other_matches:
        date_str = match.group(1)
        if re.search(rf"{re.escape(date_str)}T\d", line):
            continue
        if re.match(r"\d{4}-\d{2}-\d{2}$", date_str):
            continue
        invalid_format_count += 1
        violations.append(
            {
                "line": line_num,
                "content": line.strip()[:80],
                "timestamp": date_str,
                "issue": "Non-standard date format (should be YYYY-MM-DD date-only)",
            }
        )
    return invalid_format_count, violations


def _process_line_timestamps(
    line: str, line_num: int, patterns: dict[str, str]
) -> tuple[int, int, list[dict[str, object]]]:
    """Process a single line for timestamp validation.

    Returns:
        Tuple of (valid_count, invalid_count, violations)
    """
    valid_count = invalid_format_count = 0
    violations: list[dict[str, object]] = []

    v_count, _ = _check_valid_date_patterns(line, line_num, patterns["date"])
    valid_count += v_count

    inv_count, dt_violations = _check_invalid_datetime_patterns(
        line, line_num, patterns["datetime"]
    )
    invalid_format_count += inv_count
    violations.extend(dt_violations)

    inv_count, dt_format_violations = _check_invalid_datetime_formats(line, line_num)
    invalid_format_count += inv_count
    violations.extend(dt_format_violations)

    inv_count, o_violations = _check_other_date_formats(
        line, line_num, patterns["other"]
    )
    invalid_format_count += inv_count
    violations.extend(o_violations)

    return valid_count, invalid_format_count, violations


def scan_timestamps(content: str) -> dict[str, object]:
    """Scan content for timestamps and validate format.

    Args:
        content: File content to scan

    Returns:
        Dictionary with validation results:
        - valid_count: Number of valid YYYY-MM-DD date-only timestamps
        - invalid_format_count: Number of invalid timestamp formats (with time components or non-standard formats)
        - invalid_with_time_count: Number of timestamps with time components (must be 0)
        - violations: List of violation details
    """
    patterns = {
        "datetime": r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\b",
        "date": r"\b(\d{4}-\d{2}-\d{2})\b",
        "other": r"\b((?:\d{1,2}|\d{3})[/-]\d{1,2}[/-]\d{2,4}|\d{2,3}[/-]\d{1,2}[/-]\d{1,2})\b",
    }
    valid_count = invalid_format_count = invalid_with_time_count = 0
    violations: list[dict[str, object]] = []

    for line_num, line in enumerate(content.split("\n"), start=1):
        v_count, inv_count, line_violations = _process_line_timestamps(
            line, line_num, patterns
        )
        valid_count += v_count
        invalid_format_count += inv_count
        for violation in line_violations:
            issue = str(violation.get("issue", ""))
            if "time component" in issue:
                invalid_with_time_count += 1
        violations.extend(line_violations)

    return {
        "valid_count": valid_count,
        "invalid_format_count": invalid_format_count,
        "invalid_with_time_count": invalid_with_time_count,
        "violations": violations[:20],
    }


async def validate_timestamps_single_file(
    fs_manager: FileSystemManager, root: Path, file_name: str
) -> str:
    """Validate timestamps in a single Memory Bank file.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Name of file to validate

    Returns:
        JSON string with timestamp validation results
    """
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"}, indent=2
        )
    if not file_path.exists():
        return json.dumps(
            {"status": "error", "error": f"File {file_name} does not exist"}, indent=2
        )
    content, _ = await fs_manager.read_file(file_path)
    scan_result = scan_timestamps(content)

    invalid_format_count = cast(int, scan_result["invalid_format_count"])
    invalid_with_time_count = cast(int, scan_result["invalid_with_time_count"])
    has_blocking_violations = invalid_format_count > 0 or invalid_with_time_count > 0

    result: dict[str, object] = {
        "status": "success",
        "check_type": "timestamps",
        "file_name": file_name,
        "valid_count": scan_result["valid_count"],
        "invalid_format_count": scan_result["invalid_format_count"],
        "invalid_with_time_count": scan_result["invalid_with_time_count"],
        "violations": scan_result["violations"],
        "valid": not has_blocking_violations,
    }

    return json.dumps(result, indent=2)


def process_file_timestamps(
    file_name: str, content: str
) -> tuple[dict[str, object], int, int, int]:
    """Process timestamps for a single file.

    Returns:
        Tuple of (file_result, valid_count, invalid_format_count, invalid_with_time_count)
    """
    scan_result = scan_timestamps(content)
    valid_count = cast(int, scan_result["valid_count"])
    invalid_format_count = cast(int, scan_result["invalid_format_count"])
    invalid_with_time_count = cast(int, scan_result["invalid_with_time_count"])

    has_blocking_violations = invalid_format_count > 0 or invalid_with_time_count > 0

    file_result = {
        "valid_count": scan_result["valid_count"],
        "invalid_format_count": scan_result["invalid_format_count"],
        "invalid_with_time_count": scan_result["invalid_with_time_count"],
        "violations": scan_result["violations"],
        "valid": not has_blocking_violations,
    }

    return file_result, valid_count, invalid_format_count, invalid_with_time_count


async def validate_timestamps_all_files(
    fs_manager: FileSystemManager,
    root: Path,
    read_all_files_func: Callable[[FileSystemManager, Path], Awaitable[dict[str, str]]],
) -> str:
    """Validate timestamps across all Memory Bank files.

    Args:
        fs_manager: File system manager
        root: Project root path
        read_all_files_func: Function to read all memory bank files

    Returns:
        JSON string with timestamp validation results for all files
    """
    files_content = await read_all_files_func(fs_manager, root)
    results: dict[str, dict[str, object]] = {}
    totals = _process_all_files_timestamps(files_content, results)
    result = _build_timestamps_result(totals, results)
    return json.dumps(result, indent=2)


def _process_all_files_timestamps(
    files_content: dict[str, str], results: dict[str, dict[str, object]]
) -> tuple[int, int, int]:
    """Process timestamps for all files and populate results.

    Returns:
        Tuple of (total_valid, total_invalid_format, total_invalid_with_time)
    """
    total_valid = 0
    total_invalid_format = 0
    total_invalid_with_time = 0

    for file_name, content in files_content.items():
        file_result, v_count, inv_fmt, inv_time = process_file_timestamps(
            file_name, content
        )
        results[file_name] = file_result
        total_valid += v_count
        total_invalid_format += inv_fmt
        total_invalid_with_time += inv_time

    return total_valid, total_invalid_format, total_invalid_with_time


def _build_timestamps_result(
    totals: tuple[int, int, int], results: dict[str, dict[str, object]]
) -> dict[str, object]:
    """Build timestamp validation result dictionary.

    Args:
        totals: Tuple of (total_valid, total_invalid_format, total_invalid_with_time)
        results: Dictionary of file results

    Returns:
        Result dictionary
    """
    total_valid, total_invalid_format, total_invalid_with_time = totals
    has_any_blocking_violations = (
        total_invalid_format > 0 or total_invalid_with_time > 0
    )

    return {
        "status": "success",
        "check_type": "timestamps",
        "total_valid": total_valid,
        "total_invalid_format": total_invalid_format,
        "total_invalid_with_time": total_invalid_with_time,
        "files_valid": all(r["valid"] for r in results.values()),
        "results": results,
        "valid": not has_any_blocking_violations,
    }
