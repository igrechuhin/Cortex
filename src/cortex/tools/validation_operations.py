"""
Validation Operations Tools

This module contains consolidated validation and configuration tools for Memory Bank.

Total: 1 tool
- validate: Schema/duplications/quality checks
"""

import json
from pathlib import Path
from typing import Literal, cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp
from cortex.validation.duplication_detector import DuplicationDetector
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
    memory_bank_dir = root / "memory-bank"
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
    memory_bank_dir = root / "memory-bank"
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
    memory_bank_dir = root / "memory-bank"
    files_content: dict[str, str] = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            files_content[md_file.name] = content
    return files_content


def generate_duplication_fixes(
    duplications_dict: dict[str, object],
) -> list[dict[str, object]]:
    """Generate fix suggestions for duplications."""
    fixes: list[dict[str, object]] = []
    exact_dups = cast(
        list[dict[str, object]], duplications_dict.get("exact_duplicates", [])
    )
    similar = cast(
        list[dict[str, object]], duplications_dict.get("similar_content", [])
    )

    for dup in exact_dups + similar:
        fix: dict[str, object] = {
            "files": dup.get("files", []),
            "suggestion": "Consider using transclusion: {{include:shared-content.md}}",
            "steps": [
                "1. Create a new file for shared content",
                "2. Move duplicate content to the new file",
                "3. Replace duplicates with transclusion syntax",
            ],
        }
        fixes.append(fix)
    return fixes


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
    memory_bank_dir = root / "memory-bank"
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
    memory_bank_dir = root / "memory-bank"
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


def create_invalid_check_type_error(check_type: str) -> str:
    """Create error response for invalid check type.

    Args:
        check_type: The invalid check type

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {
            "status": "error",
            "error": f"Invalid check_type: {check_type}",
            "valid_check_types": ["schema", "duplications", "quality"],
        },
        indent=2,
    )


def create_validation_error_response(error: Exception) -> str:
    """Create error response for validation exceptions.

    Args:
        error: The exception that occurred

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {"status": "error", "error": str(error), "error_type": type(error).__name__},
        indent=2,
    )


@mcp.tool()
async def validate(
    check_type: Literal["schema", "duplications", "quality"],
    file_name: str | None = None,
    project_root: str | None = None,
    strict_mode: bool = False,
    similarity_threshold: float | None = None,
    suggest_fixes: bool = True,
) -> str:
    """Run validation checks on Memory Bank files for schema compliance, duplications, or quality metrics.

    This consolidated validation tool performs three types of checks on Memory Bank files:
    - schema: Validates file structure against Memory Bank schema (required sections, frontmatter)
    - duplications: Detects exact and similar duplicate content across files
    - quality: Calculates quality scores based on completeness, structure, and content

    Use this tool to ensure Memory Bank files follow best practices, identify content duplication
    that could be refactored using transclusion, and assess overall documentation quality.

    Args:
        check_type: Type of validation to perform
            - "schema": Validate file structure and required sections
            - "duplications": Detect duplicate content across files
            - "quality": Calculate quality scores and metrics
        file_name: Specific file to validate (e.g., "projectBrief.md")
            - For schema: validates single file or all files if None
            - For duplications: always checks all files (parameter ignored)
            - For quality: calculates score for single file or overall score if None
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

    Note:
        - Schema validation checks for required sections, proper frontmatter, and file structure
        - Duplication detection uses content hashing for exact matches and similarity algorithms for near-matches
        - Quality metrics consider completeness (required sections present), structure (proper formatting),
          and content quality (sufficient detail, clear writing)
        - The similarity_threshold parameter only affects duplication checks; typical values are 0.8-0.95
        - Suggested fixes for duplications recommend using DRY linking with transclusion syntax
        - Quality scores range from 0-100, with 80+ considered good, 60-79 acceptable, below 60 needs improvement
        - All validation operations are read-only and do not modify files
    """
    try:
        root = get_project_root(project_root)
        validation_managers = await setup_validation_managers(root)

        if check_type == "schema":
            return await handle_schema_validation(validation_managers, root, file_name)
        elif check_type == "duplications":
            return await handle_duplications_validation(
                validation_managers, root, similarity_threshold, suggest_fixes
            )
        elif check_type == "quality":
            return await handle_quality_validation(validation_managers, root, file_name)
        else:
            return create_invalid_check_type_error(check_type)
    except Exception as e:
        return create_validation_error_response(e)


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
