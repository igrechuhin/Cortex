"""
Validation Operations Tools

This module contains consolidated validation and configuration tools for Memory Bank.

Total: 1 tool
- validate: Schema/duplications/quality checks
"""

from cortex.server import mcp
from cortex.tools.validation_dispatch import (
    CheckType,
    call_dispatch_validation,
    prepare_validation_managers,
)
from cortex.tools.validation_helpers import create_validation_error_response


@mcp.tool()
async def validate(
    check_type: CheckType,
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
    """Run validation checks on Memory Bank files for schema compliance,
    duplications, quality metrics, or timestamps.

    This consolidated validation tool performs six types of checks:
    - schema: Validates file structure against Memory Bank schema
      (required sections, frontmatter)
    - duplications: Detects exact and similar duplicate content across files
    - quality: Calculates quality scores based on completeness, structure,
      and content
    - infrastructure: Validates project infrastructure consistency
      (CI vs commit prompt, code quality, docs, config)
    - timestamps: Validates that all timestamps use YYYY-MM-DDTHH:MM format
      (ISO 8601 date-time without seconds/timezone)
    - roadmap_sync: Validates that roadmap.md is synchronized with codebase
      (all production TODOs tracked, all references valid)

    Use this tool to ensure Memory Bank files follow best practices,
    identify content duplication that could be refactored using transclusion,
    assess overall documentation quality, and validate project infrastructure
    consistency.

    Args:
        check_type: Type of validation to perform
            - "schema": Validate file structure and required sections
            - "duplications": Detect duplicate content across files
            - "quality": Calculate quality scores and metrics
            - "roadmap_sync": Validate roadmap.md synchronization with codebase
            - "infrastructure": Validate project infrastructure consistency
            - "timestamps": Validate timestamp format (YYYY-MM-DDTHH:MM,
              ISO 8601 date-time without seconds/timezone)
        file_name: Specific file to validate (e.g., "projectBrief.md")
            - For schema: validates single file or all files if None
            - For duplications: always checks all files (parameter ignored)
            - For quality: calculates score for single file or overall
              score if None
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
        check_commit_ci_alignment: Check commit prompt vs CI workflow
            alignment (default: True)
            - Only applicable for check_type="infrastructure"
        check_code_quality_consistency: Check code quality standards
            consistency (default: True)
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
            "activeContext.md": {
                "valid": false,
                "errors": ["Missing required section: Current Work"],
                "warnings": []
            }
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
              "locations": [{"file": "systemPatterns.md", "line": 15},
              {"file": "techContext.md", "line": 42}]
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
              "suggestion": (
                  "Consider using transclusion: "
                  "{{include:shared-content.md}}"
              ),
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
           Input: validate(check_type="duplications", similarity_threshold=0.85,
           suggest_fixes=True)
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
                 "suggestion": (
                  "Consider using transclusion: "
                  "{{include:shared-content.md}}"
              ),
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

        6. Validate roadmap synchronization:
           Input: validate(check_type="roadmap_sync")
           Output:
           {
             "status": "success",
             "check_type": "roadmap_sync",
             "valid": false,
             "missing_roadmap_entries": [
               {
                 "file_path": "src/cortex/tools/pre_commit_tools.py",
                 "line": 56,
                 "snippet": "# TODO: Add other language adapters as needed",
                 "category": "todo"
               }
             ],
             "invalid_references": [
               {
                 "file_path": "src/cortex/core/old_module.py",
                 "line": 42,
                 "context": "See old_module.py:42 for details",
                 "phase": "Phase 5: Refactoring"
               }
             ],
             "warnings": [
               (
                  "Reference to src/cortex/core/token_counter.py:500 "
                  "exceeds file length (458 lines)"
              )
             ],
             "summary": {
               "total_todos_found": 1,
               "missing_entries_count": 1,
               "invalid_references_count": 1,
               "warnings_count": 1
             }
           }

    Note:
        - Schema validation checks for required sections, proper frontmatter,
        and file structure
        - Duplication detection uses content hashing for exact matches and
          similarity algorithms for near-matches
        - Quality metrics consider completeness (required sections present),
        structure (proper formatting),
          and content quality (sufficient detail, clear writing)
        - Infrastructure validation checks project consistency
          (CI vs commit prompt, code quality, docs, config)
        - Timestamp validation ensures all timestamps use YYYY-MM-DDTHH:MM
          format (ISO 8601 date-time without seconds/timezone)
        - Roadmap sync validation ensures all production TODOs are tracked
          in roadmap.md and all roadmap references are valid
        - The similarity_threshold parameter only affects duplication checks;
          typical values are 0.8-0.95
        - Suggested fixes for duplications recommend using DRY linking
          with transclusion syntax
        - Quality scores range from 0-100, with 80+ considered good, 60-79 acceptable,
        below 60 needs improvement
        - All validation operations are read-only and do not modify files
    """
    return await _execute_validation_with_error_handling(
        check_type,
        project_root,
        file_name,
        similarity_threshold,
        suggest_fixes,
        check_commit_ci_alignment,
        check_code_quality_consistency,
        check_documentation_consistency,
        check_config_consistency,
    )


async def _execute_validation_with_error_handling(
    check_type: CheckType,
    project_root: str | None,
    file_name: str | None,
    similarity_threshold: float | None,
    suggest_fixes: bool,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> str:
    """Execute validation with error handling."""
    try:
        root, managers = await prepare_validation_managers(project_root)
        return await call_dispatch_validation(
            check_type,
            managers,
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
