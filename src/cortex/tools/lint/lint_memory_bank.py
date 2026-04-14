"""Memory-bank lint helpers: report model and check builder.

The MCP tool surface has been removed. These helpers are called internally
by autofix and the analyze pipeline — not exposed as a standalone tool.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.tools.lint.memory_bank_lint_checks import (
    CodeClaimCheck,
    CrossRefCheck,
    IndexStalenessCheck,
    LintCheck,
    LintFinding,
    MissingPlanFilesCheck,
    OrphanedPlansCheck,
    StaleActiveContextCheck,
    StaleNumericClaimCheck,
    load_lint_config,
)
from cortex.tools.lint.memory_bank_wiki_checks import OrphanedWikiPagesCheck


class LintReport(BaseModel):
    """Structured output for memory-bank lint runs."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    findings: list[LintFinding] = Field(
        default_factory=lambda: list[LintFinding](),
        description="All findings emitted by enabled checks",
    )
    summary: str = Field(description="Human-readable summary of lint run")
    error_count: int = Field(ge=0, description="Number of error findings")
    warning_count: int = Field(ge=0, description="Number of warning findings")
    info_count: int = Field(ge=0, description="Number of info findings")


def build_memory_bank_lint_checks(project_root: Path) -> list[LintCheck]:
    """Return all currently supported memory-bank lint checks."""
    config = load_lint_config(project_root)
    stale_threshold_days = 30 if config is None else config.stale_threshold_days
    return [
        OrphanedPlansCheck(),
        MissingPlanFilesCheck(),
        StaleActiveContextCheck(stale_threshold_days=stale_threshold_days),
        CrossRefCheck(),
        OrphanedWikiPagesCheck(),
        IndexStalenessCheck(),
        StaleNumericClaimCheck(),
        CodeClaimCheck(),
    ]
