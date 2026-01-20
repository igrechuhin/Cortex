"""Timestamp validation utilities for Memory Bank files.

This module provides functions to validate timestamp formats in Memory Bank files.
Valid timestamps use YYYY-MM-DDTHH:MM format (ISO 8601 date-time without seconds/timezone).
"""

import json
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

# Valid format: YYYY-MM-DDTHH:MM (ISO 8601 without seconds/timezone)
VALID_DATETIME_PATTERN = r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\b"
# Also valid: YYYY-MM-DD (date-only for historical entries)
VALID_DATE_PATTERN = r"\b(\d{4}-\d{2}-\d{2})\b"


def _check_valid_datetime_patterns(
    line: str, line_num: int
) -> tuple[int, list[dict[str, object]]]:
    """Check for valid YYYY-MM-DDTHH:MM format timestamps.

    Returns:
        Tuple of (valid_count, violations)
    """
    valid_count = 0
    violations: list[dict[str, object]] = []
    datetime_matches = re.finditer(VALID_DATETIME_PATTERN, line)
    for match in datetime_matches:
        timestamp_str = match.group(1)
        try:
            _ = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M")
            valid_count += 1
        except ValueError:
            pass
    return valid_count, violations


def _check_valid_date_patterns(
    line: str, line_num: int
) -> tuple[int, list[dict[str, object]]]:
    """Check for valid YYYY-MM-DD date-only format timestamps.

    Date-only format is also valid for historical entries or when time is not needed.

    Returns:
        Tuple of (valid_count, violations)
    """
    valid_count = 0
    violations: list[dict[str, object]] = []
    date_matches = re.finditer(VALID_DATE_PATTERN, line)
    for match in date_matches:
        date_str = match.group(1)
        # Skip if this is part of a datetime (YYYY-MM-DDTHH:MM)
        if re.search(rf"{re.escape(date_str)}T\d", line):
            continue
        try:
            _ = datetime.strptime(date_str, "%Y-%m-%d")
            valid_count += 1
        except ValueError:
            pass
    return valid_count, violations


def _get_invalid_datetime_patterns() -> list[tuple[str, str]]:
    """Get patterns for invalid datetime formats.

    Invalid formats include:
    - Timestamps with seconds (YYYY-MM-DDTHH:MM:SS)
    - Timestamps with timezone (YYYY-MM-DDTHH:MMZ or YYYY-MM-DDTHH:MM+00:00)
    - Space-separated date-time (YYYY-MM-DD HH:MM)

    Returns:
        List of (pattern, issue_message) tuples
    """
    return [
        (
            r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\b",
            "Invalid format: space-separated (should be YYYY-MM-DDTHH:MM)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\b",
            "Invalid format: contains seconds (should be YYYY-MM-DDTHH:MM)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[Z+-]",
            "Invalid format: contains timezone (should be YYYY-MM-DDTHH:MM)",
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
    line: str, line_num: int
) -> tuple[int, list[dict[str, object]]]:
    """Check for other non-standard date formats.

    Returns:
        Tuple of (invalid_count, violations)
    """
    invalid_format_count = 0
    violations: list[dict[str, object]] = []
    # Match formats like MM/DD/YYYY, DD-MM-YYYY, etc.
    other_pattern = r"\b((?:\d{1,2}|\d{3})[/-]\d{1,2}[/-]\d{2,4})\b"
    other_matches = re.finditer(other_pattern, line)
    for match in other_matches:
        date_str = match.group(1)
        # Skip if it matches valid YYYY-MM-DD format
        if re.match(r"\d{4}-\d{2}-\d{2}$", date_str):
            continue
        invalid_format_count += 1
        violations.append(
            {
                "line": line_num,
                "content": line.strip()[:80],
                "timestamp": date_str,
                "issue": "Non-standard date format (use YYYY-MM-DD or YYYY-MM-DDTHH:MM)",
            }
        )
    return invalid_format_count, violations


def _process_line_timestamps(
    line: str, line_num: int
) -> tuple[int, int, list[dict[str, object]]]:
    """Process a single line for timestamp validation.

    Returns:
        Tuple of (valid_count, invalid_count, violations)
    """
    valid_count = invalid_format_count = 0
    violations: list[dict[str, object]] = []

    # Check for valid YYYY-MM-DDTHH:MM format (preferred)
    v_count, _ = _check_valid_datetime_patterns(line, line_num)
    valid_count += v_count

    # Check for valid YYYY-MM-DD format (also acceptable)
    v_count, _ = _check_valid_date_patterns(line, line_num)
    valid_count += v_count

    # Check for invalid formats
    inv_count, inv_violations = _check_invalid_datetime_formats(line, line_num)
    invalid_format_count += inv_count
    violations.extend(inv_violations)

    inv_count, o_violations = _check_other_date_formats(line, line_num)
    invalid_format_count += inv_count
    violations.extend(o_violations)

    return valid_count, invalid_format_count, violations


def scan_timestamps(content: str) -> dict[str, object]:
    """Scan content for timestamps and validate format.

    Args:
        content: File content to scan

    Returns:
        Dictionary with validation results:
        - valid_count: Number of valid timestamps (YYYY-MM-DDTHH:MM or YYYY-MM-DD)
        - invalid_format_count: Number of invalid timestamp formats
        - violations: List of violation details
    """
    valid_count = invalid_format_count = 0
    violations: list[dict[str, object]] = []

    for line_num, line in enumerate(content.split("\n"), start=1):
        v_count, inv_count, line_violations = _process_line_timestamps(line, line_num)
        valid_count += v_count
        invalid_format_count += inv_count
        violations.extend(line_violations)

    return {
        "valid_count": valid_count,
        "invalid_format_count": invalid_format_count,
        "invalid_with_time_count": 0,  # Deprecated: time component is now valid
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
    has_blocking_violations = invalid_format_count > 0

    result: dict[str, object] = {
        "status": "success",
        "check_type": "timestamps",
        "file_name": file_name,
        "valid_count": scan_result["valid_count"],
        "invalid_format_count": scan_result["invalid_format_count"],
        "invalid_with_time_count": 0,  # Deprecated
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

    has_blocking_violations = invalid_format_count > 0

    file_result = {
        "valid_count": scan_result["valid_count"],
        "invalid_format_count": scan_result["invalid_format_count"],
        "invalid_with_time_count": 0,  # Deprecated
        "violations": scan_result["violations"],
        "valid": not has_blocking_violations,
    }

    return file_result, valid_count, invalid_format_count, 0


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

    for file_name, content in files_content.items():
        file_result, v_count, inv_fmt, _ = process_file_timestamps(file_name, content)
        results[file_name] = file_result
        total_valid += v_count
        total_invalid_format += inv_fmt

    return total_valid, total_invalid_format, 0


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
    total_valid, total_invalid_format, _ = totals
    has_any_blocking_violations = total_invalid_format > 0

    return {
        "status": "success",
        "check_type": "timestamps",
        "total_valid": total_valid,
        "total_invalid_format": total_invalid_format,
        "total_invalid_with_time": 0,  # Deprecated
        "files_valid": all(r["valid"] for r in results.values()),
        "results": results,
        "valid": not has_any_blocking_violations,
    }
