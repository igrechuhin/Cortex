"""
Validation Operations Tools

This module contains consolidated validation and configuration tools for Memory Bank.

Total: 1 tool
- validate: Schema/duplications/quality checks
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.validation.dispatch import (
    call_dispatch_validation,
    prepare_validation_managers,
)
from cortex.tools.validation.helpers import (
    ValidationCheckType,
    create_invalid_check_type_error,
    create_validation_error_response,
    parse_validation_check_type,
)
from cortex.tools.validation.response_formatters import (
    format_validate_response,
)

# Type alias for check_type (must match ValidationCheckType enum).
ValidateCheckTypeName = ValidationCheckType

VALIDATE_INPUT_EXAMPLES: list[dict[str, object]] = [
    {"check_type": "schema", "file_name": MemoryBankFile.PROJECT_BRIEF},
    {"check_type": "duplications", "similarity_threshold": 0.8},
    {"check_type": "roadmap_sync"},
]


def _get_session_default_check_type() -> ValidateCheckTypeName:
    """Resolve zero-arg validate() default from session config."""
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    raw = str(cfg.get("check_type", "timestamps"))
    parsed = parse_validation_check_type(raw)
    return parsed or ValidationCheckType("timestamps")


async def validate_impl(
    parsed: ValidateCheckTypeName,
    file_name: str | None,
    similarity_threshold: float | None,
    suggest_fixes: bool,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
    ctx: MCPContext | None,
    response_format: ResponseFormat,
) -> str:
    raw = await _execute_validation_with_error_handling(
        parsed,
        file_name,
        similarity_threshold,
        suggest_fixes,
        check_commit_ci_alignment,
        check_code_quality_consistency,
        check_documentation_consistency,
        check_config_consistency,
        ctx,
    )
    return format_validate_response(raw, parsed, response_format)


# MCP tool removed — exposed as resource cortex://validation/{check_type}
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def validate(
    check_type: ValidateCheckTypeName | None = None,
    file_name: str | None = None,
    strict_mode: bool = False,
    similarity_threshold: float | None = None,
    suggest_fixes: bool = True,
    check_commit_ci_alignment: bool = True,
    check_code_quality_consistency: bool = True,
    check_documentation_consistency: bool = True,
    check_config_consistency: bool = True,
    response_format: ResponseFormat = ResponseFormat.CONCISE,
    ctx: MCPContext | None = None,
) -> str:
    """Run validation checks on Memory Bank files for schema compliance,
    duplications, quality metrics, or timestamps.

    USE WHEN: User wants to validate memory bank, user needs quality check,
    user reports schema issues, user requests validation, user wants to check
    for duplicates.

    EXAMPLES: 'validate schema', 'check for duplications', 'validate quality
    metrics', 'validate infrastructure consistency', 'check timestamp format',
    'validate roadmap sync'.

    RETURNS: JSON with validation results, errors found, and suggested fixes.

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

    Input examples (for tool selection):
        - Basic: check_type="schema", file_name="projectBrief.md"
        - All files: check_type="schema" (file_name omitted)
        - Duplications: check_type="duplications", similarity_threshold=0.8
        - Infrastructure: check_type="infrastructure", check_commit_ci_alignment=True
        - Roadmap sync: check_type="roadmap_sync"

    Returns:
        JSON string. Success: status, check_type, and type-specific fields
        (validation, results, duplicates_found, overall_score, etc.).
        Error: status "error", error, error_type.

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
          in roadmap.md and all roadmap references are valid. When valid is
          false, the response includes missing_roadmap_entries,
          invalid_references, and unlinked_plans for actionable fixes.
        - The similarity_threshold parameter only affects duplication checks;
          typical values are 0.8-0.95
        - Suggested fixes for duplications recommend using DRY linking
          with transclusion syntax
        - Quality scores range from 0-100, with 80+ considered good, 60-79 acceptable,
        below 60 needs improvement
        - All validation operations are read-only and do not modify files
    """
    await log_client(ctx, "info", "validate: starting", logger_name=__name__)
    check_type = check_type or _get_session_default_check_type()
    parsed = parse_validation_check_type(check_type)
    if parsed is None:
        await log_client(ctx, "warning", "validate: invalid check_type")
        return create_invalid_check_type_error(check_type or "null")
    return await validate_impl(
        parsed,
        file_name,
        similarity_threshold,
        suggest_fixes,
        check_commit_ci_alignment,
        check_code_quality_consistency,
        check_documentation_consistency,
        check_config_consistency,
        ctx,
        response_format,
    )


async def _execute_validation_with_error_handling(
    check_type: ValidationCheckType,
    file_name: str | None,
    similarity_threshold: float | None,
    suggest_fixes: bool,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
    ctx: MCPContext | None,
) -> str:
    """Execute validation with error handling."""
    try:
        resolved_root = await resolve_project_root_async(None, ctx)
        root, managers = await prepare_validation_managers(str(resolved_root))
        result = await call_dispatch_validation(
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
        await log_client(ctx, "info", "validate: completed", logger_name=__name__)
        return result
    except Exception as e:
        await log_client(ctx, "error", f"validate: failed: {e}", logger_name=__name__)
        return create_validation_error_response(e)


@mcp.resource(uri="cortex://validation")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def validate_resource() -> str:
    """Resource: Run validation. Zero-arg — reads check_type from session config.

    Falls back to "timestamps" if no session config exists. check_type must be
    one of: schema, duplications, quality, infrastructure, timestamps, roadmap_sync.
    """
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    ct = str(cfg.get("check_type", "timestamps"))
    parsed = parse_validation_check_type(ct)
    if parsed is None:
        return create_invalid_check_type_error(ct)
    return await _execute_validation_with_error_handling(
        parsed,
        None,
        None,
        True,
        True,
        True,
        True,
        True,
        None,
    )
