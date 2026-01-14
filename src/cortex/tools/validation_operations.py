"""
Validation Operations Tools

This module contains consolidated validation and configuration tools for Memory Bank.

Total: 1 tool
- validate: Schema/duplications/quality checks
"""

import json
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeAlias, cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp
from cortex.tools.validation_helpers import (
    create_invalid_check_type_error,
    create_validation_error_response,
    generate_duplication_fixes,
)
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.infrastructure_validator import InfrastructureValidator
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.validation_config import ValidationConfig


async def validate_schema_single_file(
    fs_manager: FileSystemManager,
    schema_validator: SchemaValidator,
    root: Path,
    file_name: str,
) -> str:
    """Validate a single file against schema."""
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
    validation_result = await schema_validator.validate_file(file_name, content)
    return json.dumps(
        {
            "status": "success",
            "check_type": "schema",
            "file_name": file_name,
            "validation": validation_result,
        },
        indent=2,
    )


async def validate_schema_all_files(
    fs_manager: FileSystemManager, schema_validator: SchemaValidator, root: Path
) -> str:
    """Validate all files against schema."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    results_dict: dict[str, object] = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            validation_result = await schema_validator.validate_file(
                md_file.name, content
            )
            results_dict[md_file.name] = validation_result
    return json.dumps(
        {"status": "success", "check_type": "schema", "results": results_dict},
        indent=2,
    )


async def read_all_memory_bank_files(
    fs_manager: FileSystemManager, root: Path
) -> dict[str, str]:
    """Read all markdown files in memory-bank directory."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    files_content: dict[str, str] = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            files_content[md_file.name] = content
    return files_content


def _check_valid_datetime_patterns(
    line: str, line_num: int, datetime_pattern: str
) -> tuple[int, list[dict[str, object]]]:
    """Check for valid YYYY-MM-DDTHH:MM format timestamps.

    Returns:
        Tuple of (valid_count, violations)
    """
    valid_count = 0
    violations: list[dict[str, object]] = []
    datetime_matches = re.finditer(datetime_pattern, line)
    for match in datetime_matches:
        timestamp_str = match.group(0)
        try:
            _ = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M")
            valid_count += 1
        except ValueError:
            violations.append(
                {
                    "line": line_num,
                    "content": line.strip()[:80],
                    "timestamp": timestamp_str,
                    "issue": "Invalid timestamp (not a valid calendar date/time)",
                }
            )
    return valid_count, violations


def _check_invalid_date_only_patterns(
    line: str, line_num: int, date_pattern: str
) -> tuple[int, list[dict[str, object]]]:
    """Check for date-only patterns (YYYY-MM-DD without time).

    These are invalid as timestamps must include time component.

    Returns:
        Tuple of (invalid_count, violations)
    """
    invalid_format_count = 0
    violations: list[dict[str, object]] = []
    date_matches = re.finditer(date_pattern, line)
    for match in date_matches:
        date_str = match.group(1)
        if re.search(rf"{re.escape(date_str)}T\d", line):
            continue
        try:
            _ = datetime.strptime(date_str, "%Y-%m-%d")
            invalid_format_count += 1
            violations.append(
                {
                    "line": line_num,
                    "content": line.strip()[:80],
                    "timestamp": date_str,
                    "issue": "Missing time component (should be YYYY-MM-DDTHH:MM)",
                }
            )
        except ValueError:
            pass
    return invalid_format_count, violations


def _get_invalid_datetime_patterns() -> list[tuple[str, str]]:
    """Get patterns for invalid datetime formats.

    Returns:
        List of (pattern, issue_message) tuples
    """
    return [
        (
            r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\b",
            "Space separator (should use T: YYYY-MM-DDTHH:MM)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\b",
            "Contains seconds (should be YYYY-MM-DDTHH:MM)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[Z+-]\d{2}:\d{2}\b",
            "Contains timezone (should be YYYY-MM-DDTHH:MM)",
        ),
        (
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\b",
            "Contains timezone (should be YYYY-MM-DDTHH:MM)",
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
    """Check for other non-standard date formats.

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
        invalid_format_count += 1
        violations.append(
            {
                "line": line_num,
                "content": line.strip()[:80],
                "timestamp": date_str,
                "issue": "Non-standard date format (should be YYYY-MM-DDTHH:MM)",
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

    v_count, dt_violations = _check_valid_datetime_patterns(
        line, line_num, patterns["datetime"]
    )
    valid_count += v_count
    violations.extend(dt_violations)

    inv_count, date_violations = _check_invalid_date_only_patterns(
        line, line_num, patterns["date"]
    )
    invalid_format_count += inv_count
    violations.extend(date_violations)

    inv_count, dt_format_violations = _check_invalid_datetime_formats(line, line_num)
    invalid_format_count += inv_count
    violations.extend(dt_format_violations)

    inv_count, o_violations = _check_other_date_formats(
        line, line_num, patterns["other"]
    )
    invalid_format_count += inv_count
    violations.extend(o_violations)

    return valid_count, invalid_format_count, violations


def _scan_timestamps(content: str) -> dict[str, object]:
    """Scan content for timestamps and validate format.

    Args:
        content: File content to scan

    Returns:
        Dictionary with validation results:
        - valid_count: Number of valid YYYY-MM-DDTHH:MM timestamps
        - invalid_format_count: Number of invalid timestamp formats
        - invalid_with_time_count: Number of dates with incorrect time format (deprecated, kept for compatibility)
        - violations: List of violation details
    """
    patterns = {
        "datetime": r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\b",
        "date": r"\b(\d{4}-\d{2}-\d{2})\b",
        "other": r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\b",
    }
    valid_count = invalid_format_count = invalid_with_time_count = 0
    violations: list[dict[str, object]] = []

    for line_num, line in enumerate(content.split("\n"), start=1):
        v_count, inv_count, line_violations = _process_line_timestamps(
            line, line_num, patterns
        )
        valid_count += v_count
        invalid_format_count += inv_count
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
    scan_result = _scan_timestamps(content)

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


def _process_file_timestamps(
    file_name: str, content: str
) -> tuple[dict[str, object], int, int, int]:
    """Process timestamps for a single file.

    Returns:
        Tuple of (file_result, valid_count, invalid_format_count, invalid_with_time_count)
    """
    scan_result = _scan_timestamps(content)
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
    fs_manager: FileSystemManager, root: Path
) -> str:
    """Validate timestamps across all Memory Bank files.

    Args:
        fs_manager: File system manager
        root: Project root path

    Returns:
        JSON string with timestamp validation results for all files
    """
    files_content = await read_all_memory_bank_files(fs_manager, root)
    results: dict[str, dict[str, object]] = {}
    total_valid = 0
    total_invalid_format = 0
    total_invalid_with_time = 0

    for file_name, content in files_content.items():
        file_result, v_count, inv_fmt, inv_time = _process_file_timestamps(
            file_name, content
        )
        results[file_name] = file_result
        total_valid += v_count
        total_invalid_format += inv_fmt
        total_invalid_with_time += inv_time

    has_any_blocking_violations = (
        total_invalid_format > 0 or total_invalid_with_time > 0
    )

    result: dict[str, object] = {
        "status": "success",
        "check_type": "timestamps",
        "total_valid": total_valid,
        "total_invalid_format": total_invalid_format,
        "total_invalid_with_time": total_invalid_with_time,
        "files_valid": all(r["valid"] for r in results.values()),
        "results": results,
        "valid": not has_any_blocking_violations,
    }

    return json.dumps(result, indent=2)


async def validate_duplications(
    fs_manager: FileSystemManager,
    duplication_detector: DuplicationDetector,
    validation_config: ValidationConfig,
    root: Path,
    similarity_threshold: float | None,
    suggest_fixes: bool,
) -> str:
    """Detect duplicate content across files."""
    threshold = similarity_threshold or validation_config.get_duplication_threshold()
    files_content = await read_all_memory_bank_files(fs_manager, root)
    duplication_detector.threshold = threshold
    duplications_dict = await duplication_detector.scan_all_files(files_content)

    duplication_result: dict[str, object] = {
        "status": "success",
        "check_type": "duplications",
        "threshold": threshold,
    }
    duplication_result.update(duplications_dict)

    duplicates_found = cast(int, duplications_dict.get("duplicates_found", 0))
    if suggest_fixes and duplicates_found > 0:
        duplication_result["suggested_fixes"] = generate_duplication_fixes(
            duplications_dict
        )

    return json.dumps(duplication_result, indent=2)


async def validate_quality_single_file(
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    quality_metrics: QualityMetrics,
    root: Path,
    file_name: str,
) -> str:
    """Calculate quality score for a single file."""
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
    file_metadata = await metadata_index.get_file_metadata(file_name)
    metadata = file_metadata or {}
    score = await quality_metrics.calculate_file_score(file_name, content, metadata)
    return json.dumps(
        {
            "status": "success",
            "check_type": "quality",
            "file_name": file_name,
            "score": score,
        },
        indent=2,
    )


async def validate_quality_all_files(
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    quality_metrics: QualityMetrics,
    duplication_detector: DuplicationDetector,
    root: Path,
) -> str:
    """Calculate overall quality score for all files."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    all_files_content: dict[str, str] = {}
    files_metadata: dict[str, dict[str, object]] = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            all_files_content[md_file.name] = content
            file_meta = await metadata_index.get_file_metadata(md_file.name)
            files_metadata[md_file.name] = file_meta or {}
    duplication_data = await duplication_detector.scan_all_files(all_files_content)
    overall_score = await quality_metrics.calculate_overall_score(
        all_files_content, files_metadata, duplication_data
    )
    result: dict[str, object] = {"status": "success", "check_type": "quality"}
    for key, value in overall_score.items():
        if key != "status":
            result[key] = value
        else:
            result["health_status"] = value
    return json.dumps(result, indent=2)


async def handle_schema_validation(
    validation_managers: dict[
        str,
        FileSystemManager
        | MetadataIndex
        | SchemaValidator
        | DuplicationDetector
        | QualityMetrics
        | ValidationConfig,
    ],
    root: Path,
    file_name: str | None,
) -> str:
    """Handle schema validation routing.

    Args:
        validation_managers: Dictionary of validation managers
        root: Project root path
        file_name: Optional specific file to validate

    Returns:
        JSON string with schema validation results
    """
    if file_name:
        return await validate_schema_single_file(
            cast(FileSystemManager, validation_managers["fs_manager"]),
            cast(SchemaValidator, validation_managers["schema_validator"]),
            root,
            file_name,
        )
    else:
        return await validate_schema_all_files(
            cast(FileSystemManager, validation_managers["fs_manager"]),
            cast(SchemaValidator, validation_managers["schema_validator"]),
            root,
        )


async def handle_duplications_validation(
    validation_managers: dict[
        str,
        FileSystemManager
        | MetadataIndex
        | SchemaValidator
        | DuplicationDetector
        | QualityMetrics
        | ValidationConfig,
    ],
    root: Path,
    similarity_threshold: float | None,
    suggest_fixes: bool,
) -> str:
    """Handle duplications validation.

    Args:
        validation_managers: Dictionary of validation managers
        root: Project root path
        similarity_threshold: Threshold for duplications
        suggest_fixes: Whether to include fix suggestions

    Returns:
        JSON string with duplications validation results
    """
    return await validate_duplications(
        cast(FileSystemManager, validation_managers["fs_manager"]),
        cast(DuplicationDetector, validation_managers["duplication_detector"]),
        cast(ValidationConfig, validation_managers["validation_config"]),
        root,
        similarity_threshold,
        suggest_fixes,
    )


async def handle_quality_validation(
    validation_managers: dict[
        str,
        FileSystemManager
        | MetadataIndex
        | SchemaValidator
        | DuplicationDetector
        | QualityMetrics
        | ValidationConfig,
    ],
    root: Path,
    file_name: str | None,
) -> str:
    """Handle quality validation routing.

    Args:
        validation_managers: Dictionary of validation managers
        root: Project root path
        file_name: Optional specific file to validate

    Returns:
        JSON string with quality validation results
    """
    if file_name:
        return await validate_quality_single_file(
            cast(FileSystemManager, validation_managers["fs_manager"]),
            cast(MetadataIndex, validation_managers["metadata_index"]),
            cast(QualityMetrics, validation_managers["quality_metrics"]),
            root,
            file_name,
        )
    else:
        return await validate_quality_all_files(
            cast(FileSystemManager, validation_managers["fs_manager"]),
            cast(MetadataIndex, validation_managers["metadata_index"]),
            cast(QualityMetrics, validation_managers["quality_metrics"]),
            cast(DuplicationDetector, validation_managers["duplication_detector"]),
            root,
        )


async def handle_infrastructure_validation(
    root: Path,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> str:
    """Handle infrastructure validation.

    Args:
        root: Project root path
        check_commit_ci_alignment: Check commit prompt vs CI workflow alignment
        check_code_quality_consistency: Check code quality standards consistency
        check_documentation_consistency: Check documentation consistency
        check_config_consistency: Check configuration consistency

    Returns:
        JSON string with infrastructure validation results
    """
    validator = InfrastructureValidator(root)
    result = await validator.validate_infrastructure(
        check_commit_ci_alignment=check_commit_ci_alignment,
        check_code_quality_consistency=check_code_quality_consistency,
        check_documentation_consistency=check_documentation_consistency,
        check_config_consistency=check_config_consistency,
    )
    return json.dumps(result, indent=2)


async def handle_timestamps_validation(
    validation_managers: dict[
        str,
        FileSystemManager
        | MetadataIndex
        | SchemaValidator
        | DuplicationDetector
        | QualityMetrics
        | ValidationConfig,
    ],
    root: Path,
    file_name: str | None,
) -> str:
    """Handle timestamps validation routing.

    Args:
        validation_managers: Dictionary of validation managers
        root: Project root path
        file_name: Optional specific file to validate

    Returns:
        JSON string with timestamps validation results
    """
    if file_name:
        return await validate_timestamps_single_file(
            cast(FileSystemManager, validation_managers["fs_manager"]),
            root,
            file_name,
        )
    else:
        return await validate_timestamps_all_files(
            cast(FileSystemManager, validation_managers["fs_manager"]),
            root,
        )


@mcp.tool()
async def validate(
    check_type: Literal[
        "schema", "duplications", "quality", "infrastructure", "timestamps"
    ],
    file_name: str | None = None,
    project_root: str | None = None,
    strict_mode: bool = False,
    similarity_threshold: float | None = None,
    suggest_fixes: bool = True,
    check_commit_ci_alignment: bool = True,
    check_code_quality_consistency: bool = True,
    check_documentation_consistency: bool = True,
    check_config_consistency: bool = True,
) -> str:
    """Run validation checks on Memory Bank files for schema compliance, duplications, quality metrics, or timestamps.

    This consolidated validation tool performs five types of checks:
    - schema: Validates file structure against Memory Bank schema (required sections, frontmatter)
    - duplications: Detects exact and similar duplicate content across files
    - quality: Calculates quality scores based on completeness, structure, and content
    - infrastructure: Validates project infrastructure consistency (CI vs commit prompt, code quality, docs, config)
    - timestamps: Validates that all timestamps use YYYY-MM-DDTHH:MM format (ISO 8601 date-time without seconds/timezone)

    Use this tool to ensure Memory Bank files follow best practices, identify content duplication
    that could be refactored using transclusion, assess overall documentation quality, and validate
    project infrastructure consistency.

    Args:
        check_type: Type of validation to perform
            - "schema": Validate file structure and required sections
            - "duplications": Detect duplicate content across files
            - "quality": Calculate quality scores and metrics
            - "infrastructure": Validate project infrastructure consistency
            - "timestamps": Validate timestamp format (YYYY-MM-DDTHH:MM, ISO 8601 date-time without seconds/timezone)
        file_name: Specific file to validate (e.g., "projectBrief.md")
            - For schema: validates single file or all files if None
            - For duplications: always checks all files (parameter ignored)
            - For quality: calculates score for single file or overall score if None
            - For infrastructure: parameter ignored (always validates entire project)
            - For timestamps: validates single file or all files if None
            Examples: "projectBrief.md", "activeContext.md", None
        project_root: Path to project root directory
            - Defaults to current working directory if None
            - Memory Bank expected at {project_root}/memory-bank/
            Example: "/Users/dev/my-project"
        strict_mode: Enable strict validation for schema checks (default: False)
            - When True, treats warnings as errors
            - Only applicable for check_type="schema"
        similarity_threshold: Similarity threshold for duplication detection (0.0-1.0)
            - Only applicable for check_type="duplications"
            - Lower values = more strict (detect more similar content)
            - Higher values = more lenient (only detect very similar content)
            - Defaults to configured threshold if None
            Example: 0.8 (detects content 80% or more similar)
        suggest_fixes: Include fix suggestions in duplication results (default: True)
            - Only applicable for check_type="duplications"
            - Provides actionable suggestions for using transclusion
        check_commit_ci_alignment: Check commit prompt vs CI workflow alignment (default: True)
            - Only applicable for check_type="infrastructure"
        check_code_quality_consistency: Check code quality standards consistency (default: True)
            - Only applicable for check_type="infrastructure"
        check_documentation_consistency: Check documentation consistency (default: True)
            - Only applicable for check_type="infrastructure"
        check_config_consistency: Check configuration consistency (default: True)
            - Only applicable for check_type="infrastructure"

    Returns:
        JSON string with validation results. Structure varies by check_type:

        Schema validation (single file):
        {
          "status": "success",
          "check_type": "schema",
          "file_name": "projectBrief.md",
          "validation": {
            "valid": true,
            "errors": [],
            "warnings": ["Missing optional section: References"]
          }
        }

        Schema validation (all files):
        {
          "status": "success",
          "check_type": "schema",
          "results": {
            "projectBrief.md": {"valid": true, "errors": [], "warnings": []},
            "activeContext.md": {"valid": false, "errors": ["Missing required section: Current Work"], "warnings": []}
          }
        }

        Duplications validation:
        {
          "status": "success",
          "check_type": "duplications",
          "threshold": 0.85,
          "duplicates_found": 2,
          "exact_duplicates": [
            {
              "content": "## Architecture Overview\nThe system uses...",
              "files": ["systemPatterns.md", "techContext.md"],
              "locations": [{"file": "systemPatterns.md", "line": 15}, {"file": "techContext.md", "line": 42}]
            }
          ],
          "similar_content": [
            {
              "similarity": 0.92,
              "files": ["productContext.md", "projectBrief.md"],
              "content_preview": "The project aims to build..."
            }
          ],
          "suggested_fixes": [
            {
              "files": ["systemPatterns.md", "techContext.md"],
              "suggestion": "Consider using transclusion: {{include:shared-content.md}}",
              "steps": [
                "1. Create a new file for shared content",
                "2. Move duplicate content to the new file",
                "3. Replace duplicates with transclusion syntax"
              ]
            }
          ]
        }

        Quality validation (single file):
        {
          "status": "success",
          "check_type": "quality",
          "file_name": "projectBrief.md",
          "score": {
            "overall": 85,
            "completeness": 90,
            "structure": 85,
            "content_quality": 80,
            "issues": ["Consider adding more examples"]
          }
        }

        Quality validation (all files):
        {
          "status": "success",
          "check_type": "quality",
          "overall_score": 78,
          "health_status": "good",
          "file_scores": {
            "projectBrief.md": 85,
            "activeContext.md": 72,
            "systemPatterns.md": 80
          },
          "metrics": {
            "total_files": 6,
            "files_above_threshold": 4,
            "average_score": 78,
            "lowest_score": 65
          },
          "recommendations": [
            "Improve activeContext.md completeness",
            "Address duplications found in systemPatterns.md"
          ]
        }

        Error response:
        {
          "status": "error",
          "error": "File projectBrief.md does not exist",
          "error_type": "FileNotFoundError"
        }

    Examples:
        1. Validate schema for a single file:
           Input: validate(check_type="schema", file_name="projectBrief.md")
           Output:
           {
             "status": "success",
             "check_type": "schema",
             "file_name": "projectBrief.md",
             "validation": {
               "valid": true,
               "errors": [],
               "warnings": ["Missing optional section: Future Considerations"]
             }
           }

        2. Detect duplications across all files with fix suggestions:
           Input: validate(check_type="duplications", similarity_threshold=0.85, suggest_fixes=True)
           Output:
           {
             "status": "success",
             "check_type": "duplications",
             "threshold": 0.85,
             "duplicates_found": 3,
             "exact_duplicates": [
               {
                 "content": "## Development Setup\nRequires Python 3.11+...",
                 "files": ["techContext.md", "README.md"],
                 "locations": [
                   {"file": "techContext.md", "line": 28},
                   {"file": "README.md", "line": 15}
                 ]
               }
             ],
             "similar_content": [
               {
                 "similarity": 0.89,
                 "files": ["systemPatterns.md", "activeContext.md"],
                 "content_preview": "The authentication system uses JWT tokens..."
               }
             ],
             "suggested_fixes": [
               {
                 "files": ["techContext.md", "README.md"],
                 "suggestion": "Consider using transclusion: {{include:shared-content.md}}",
                 "steps": [
                   "1. Create a new file for shared content",
                   "2. Move duplicate content to the new file",
                   "3. Replace duplicates with transclusion syntax"
                 ]
               }
             ]
           }

        3. Calculate quality score for all files:
           Input: validate(check_type="quality")
           Output:
           {
             "status": "success",
             "check_type": "quality",
             "overall_score": 82,
             "health_status": "good",
             "file_scores": {
               "projectBrief.md": 88,
               "productContext.md": 85,
               "activeContext.md": 78,
               "systemPatterns.md": 80,
               "techContext.md": 82,
               "progress.md": 75
             },
             "metrics": {
               "total_files": 6,
               "files_above_threshold": 5,
               "average_score": 81.3,
               "lowest_score": 75,
               "highest_score": 88
             },
             "recommendations": [
               "Improve progress.md structure and completeness",
               "Consider adding more technical details to activeContext.md"
             ]
           }

        4. Validate infrastructure consistency:
           Input: validate(check_type="infrastructure")
           Output:
           {
             "status": "success",
             "check_type": "infrastructure",
             "checks_performed": {
               "commit_ci_alignment": true,
               "code_quality_consistency": true,
               "documentation_consistency": true,
               "config_consistency": true
             },
             "issues_found": [
               {
                 "type": "missing_check",
                 "severity": "high",
                 "description": "Commit prompt missing check: check file sizes",
                 "location": ".cortex/synapse/prompts/commit.md",
                 "suggestion": "Add check file sizes check step to commit prompt",
                 "ci_check": "check file sizes",
                 "missing_in_commit": true
               }
             ],
             "recommendations": [
               "Synchronize commit prompt with CI workflow requirements"
             ]
           }

        5. Validate timestamps across all files:
           Input: validate(check_type="timestamps")
           Output:
           {
             "status": "success",
             "check_type": "timestamps",
             "total_valid": 45,
             "total_invalid_format": 0,
             "total_invalid_with_time": 2,
             "files_valid": false,
             "results": {
               "progress.md": {
                 "valid_count": 12,
                 "invalid_format_count": 0,
                 "invalid_with_time_count": 2,
                 "violations": [
                   {
                     "line": 15,
                     "content": "- ✅ Feature X - COMPLETE (2026-01-13)",
                     "timestamp": "2026-01-13",
                     "issue": "Missing time component (should be YYYY-MM-DDTHH:MM)"
                   },
                   {
                     "line": 16,
                     "content": "- ✅ Feature Y - COMPLETE (2026-01-13T12:00:00Z)",
                     "timestamp": "2026-01-13T12:00:00Z",
                     "issue": "Contains timezone (should be YYYY-MM-DDTHH:MM)"
                   }
                 ],
                 "valid": false
               },
               "roadmap.md": {
                 "valid_count": 8,
                 "invalid_format_count": 0,
                 "invalid_with_time_count": 0,
                 "violations": [],
                 "valid": true
               }
             },
             "valid": false
           }

    Note:
        - Schema validation checks for required sections, proper frontmatter, and file structure
        - Duplication detection uses content hashing for exact matches and similarity algorithms for near-matches
        - Quality metrics consider completeness (required sections present), structure (proper formatting),
          and content quality (sufficient detail, clear writing)
        - Infrastructure validation checks project consistency (CI vs commit prompt, code quality, docs, config)
        - Timestamp validation ensures all timestamps use YYYY-MM-DDTHH:MM format (ISO 8601 date-time without seconds/timezone)
        - The similarity_threshold parameter only affects duplication checks; typical values are 0.8-0.95
        - Suggested fixes for duplications recommend using DRY linking with transclusion syntax
        - Quality scores range from 0-100, with 80+ considered good, 60-79 acceptable, below 60 needs improvement
        - All validation operations are read-only and do not modify files
    """
    try:
        root = get_project_root(project_root)
        validation_managers = await setup_validation_managers(root)
        return await _dispatch_validation(
            check_type,
            cast(dict[str, object], validation_managers),
            root,
            file_name,
            similarity_threshold,
            suggest_fixes,
            check_commit_ci_alignment,
            check_code_quality_consistency,
            check_documentation_consistency,
            check_config_consistency,
        )
    except Exception as e:
        return create_validation_error_response(e)


ValidationManagers: TypeAlias = dict[
    str,
    FileSystemManager
    | MetadataIndex
    | SchemaValidator
    | DuplicationDetector
    | QualityMetrics
    | ValidationConfig,
]


def _create_validation_handlers(
    typed_managers: ValidationManagers,
    root: Path,
    file_name: str | None,
    similarity_threshold: float | None,
    suggest_fixes: bool,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> dict[str, Callable[[], Awaitable[str]]]:
    """Create validation handler functions."""
    return {
        "schema": lambda: handle_schema_validation(typed_managers, root, file_name),
        "duplications": lambda: handle_duplications_validation(
            typed_managers, root, similarity_threshold, suggest_fixes
        ),
        "quality": lambda: handle_quality_validation(typed_managers, root, file_name),
        "infrastructure": lambda: _handle_infrastructure_dispatch(
            root,
            check_commit_ci_alignment,
            check_code_quality_consistency,
            check_documentation_consistency,
            check_config_consistency,
        ),
        "timestamps": lambda: handle_timestamps_validation(
            typed_managers, root, file_name
        ),
    }


async def _dispatch_validation(
    check_type: Literal[
        "schema", "duplications", "quality", "infrastructure", "timestamps"
    ],
    validation_managers: dict[str, object],
    root: Path,
    file_name: str | None,
    similarity_threshold: float | None,
    suggest_fixes: bool,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> str:
    """Dispatch validation to appropriate handler.

    Args:
        check_type: Type of validation to perform
        validation_managers: Dictionary of validation managers
        root: Project root path
        file_name: Optional file name for single-file validation
        similarity_threshold: Similarity threshold for duplication detection
        suggest_fixes: Whether to suggest fixes for duplications
        check_commit_ci_alignment: Check commit prompt vs CI workflow alignment
        check_code_quality_consistency: Check code quality standards consistency
        check_documentation_consistency: Check documentation consistency
        check_config_consistency: Check configuration consistency

    Returns:
        JSON string with validation results
    """
    typed_managers = _get_typed_validation_managers(validation_managers)
    handlers = _create_validation_handlers(
        typed_managers,
        root,
        file_name,
        similarity_threshold,
        suggest_fixes,
        check_commit_ci_alignment,
        check_code_quality_consistency,
        check_documentation_consistency,
        check_config_consistency,
    )
    handler = handlers.get(check_type)
    if handler:
        return await handler()

    return create_invalid_check_type_error(check_type)


def _get_typed_validation_managers(
    validation_managers: dict[str, object],
) -> ValidationManagers:
    """Get typed validation managers from dict[str, object].

    Args:
        validation_managers: Dictionary of validation managers as object

    Returns:
        Typed dictionary of validation managers
    """
    # Note: dict is invariant, but we know the runtime types are correct
    return cast(
        dict[
            str,
            FileSystemManager
            | MetadataIndex
            | SchemaValidator
            | DuplicationDetector
            | QualityMetrics
            | ValidationConfig,
        ],
        validation_managers,
    )


async def _handle_infrastructure_dispatch(
    root: Path,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> str:
    """Handle infrastructure validation dispatch.

    Args:
        root: Project root path
        check_commit_ci_alignment: Check commit prompt vs CI workflow alignment
        check_code_quality_consistency: Check code quality standards consistency
        check_documentation_consistency: Check documentation consistency
        check_config_consistency: Check configuration consistency

    Returns:
        JSON string with infrastructure validation results
    """
    return await handle_infrastructure_validation(
        root,
        check_commit_ci_alignment,
        check_code_quality_consistency,
        check_documentation_consistency,
        check_config_consistency,
    )


async def setup_validation_managers(
    root: Path,
) -> dict[
    str,
    FileSystemManager
    | MetadataIndex
    | SchemaValidator
    | DuplicationDetector
    | QualityMetrics
    | ValidationConfig,
]:
    """Setup validation managers.

    Args:
        root: Project root path

    Returns:
        Dictionary with all validation managers
    """
    mgrs = await get_managers(root)
    fs_manager = cast(FileSystemManager, mgrs["fs"])
    metadata_index = cast(MetadataIndex, mgrs["index"])

    schema_validator = await get_manager(mgrs, "schema_validator", SchemaValidator)
    duplication_detector = await get_manager(
        mgrs, "duplication_detector", DuplicationDetector
    )
    quality_metrics = await get_manager(mgrs, "quality_metrics", QualityMetrics)
    validation_config = await get_manager(mgrs, "validation_config", ValidationConfig)

    return {
        "fs_manager": fs_manager,
        "metadata_index": metadata_index,
        "schema_validator": schema_validator,
        "duplication_detector": duplication_detector,
        "quality_metrics": quality_metrics,
        "validation_config": validation_config,
    }
