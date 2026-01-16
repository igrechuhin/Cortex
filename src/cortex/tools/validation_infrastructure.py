"""Infrastructure validation operations for Memory Bank files."""

import json
from pathlib import Path

from cortex.validation.infrastructure_validator import InfrastructureValidator


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
