"""Issue collection helpers for quality metrics."""

from cortex.core.models import ModelDict
from cortex.validation.models import DuplicationDataModel

from .quality_metrics_coercion import coerce_duplication_data


def add_completeness_issue(issues: list[str], completeness: float) -> None:
    """Add completeness issue if score is low."""
    if completeness < 80:
        issues.append(
            f"Completeness score is {int(completeness)}/100 - "
            + "some required sections may be missing"
        )


def add_consistency_issue(
    issues: list[str],
    consistency: float,
    duplication_data: DuplicationDataModel,
) -> None:
    """Add consistency issue if duplicates found."""
    if consistency < 80:
        if duplication_data.duplicates_found > 0:
            msg = (
                f"Found {duplication_data.duplicates_found} duplicate "
                + "or similar content sections"
            )
            issues.append(msg)


def add_freshness_issue(issues: list[str], freshness: float) -> None:
    """Add freshness issue if score is low."""
    if freshness < 60:
        issues.append(
            "Some files haven't been updated recently - " + "Memory Bank may be stale"
        )


def add_structure_issue(issues: list[str], structure: float) -> None:
    """Add structure issue if score is low."""
    if structure < 80:
        issues.append(
            "Structure issues detected - " + "check heading hierarchy and organization"
        )


def add_token_efficiency_issue(issues: list[str], token_efficiency: float) -> None:
    """Add token efficiency issue if score is low."""
    if token_efficiency < 70:
        issues.append(
            "Token usage is outside optimal range - "
            + "consider reviewing content size"
        )


def collect_all_issues(
    completeness: float,
    consistency: float,
    freshness: float,
    structure: float,
    token_efficiency: float,
    duplication_data: DuplicationDataModel | ModelDict,
) -> list[str]:
    """Collect issues based on scores."""
    issues: list[str] = []
    dup_model = coerce_duplication_data(duplication_data)

    add_completeness_issue(issues, completeness)
    add_consistency_issue(issues, consistency, dup_model)
    add_freshness_issue(issues, freshness)
    add_structure_issue(issues, structure)
    add_token_efficiency_issue(issues, token_efficiency)

    return issues
