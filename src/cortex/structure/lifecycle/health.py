"""
Structure health checking for Memory Bank.

This module handles:
- Directory validation
- Symlink validation
- Configuration file validation
- Memory bank file validation

Health score starts at 100 and is reduced by fixed penalties for each issue.
Grade mapping: A=90+, B=75-89, C=60-74, D=50-59, F=0-49.
"""

from cortex.core.constants import (
    HEALTH_GRADE_B_MIN,
    HEALTH_GRADE_C_MIN,
    HEALTH_GRADE_D_MIN,
    HEALTH_INITIAL_SCORE,
    HEALTH_PENALTY_NO_CONFIG,
    HEALTH_PENALTY_NO_MEMORY_BANK_FILES,
    HEALTH_PENALTY_PER_MISSING_DIR,
    HEALTH_SCORE_EXCELLENT,
)
from cortex.core.path_resolver import get_legacy_cursor_dir_path
from cortex.structure.models import HealthCheckResult, HealthGrade, HealthStatus
from cortex.structure.structure_config import StructureConfig


def _determine_health_grade_and_status(
    score: int,
) -> tuple[HealthGrade, HealthStatus]:
    """Determine grade and status from health score.

    Args:
        score: Health score (0-100)

    Returns:
        Tuple of (grade, status)
    """
    # Use early returns to reduce nesting; thresholds from constants
    if score >= HEALTH_SCORE_EXCELLENT:
        return HealthGrade.A, HealthStatus.HEALTHY
    if score >= HEALTH_GRADE_B_MIN:
        return HealthGrade.B, HealthStatus.GOOD
    if score >= HEALTH_GRADE_C_MIN:
        return HealthGrade.C, HealthStatus.FAIR
    if score >= HEALTH_GRADE_D_MIN:
        return HealthGrade.D, HealthStatus.WARNING
    return HealthGrade.F, HealthStatus.CRITICAL


class StructureHealthChecker:
    """Checks health of Memory Bank structure."""

    def __init__(self, config: StructureConfig):
        """Initialize health checker.

        Args:
            config: Structure configuration
        """
        self.config = config

    def check_structure_health(self) -> HealthCheckResult:
        """Check the health of the project structure.

        Validates directories, symlinks, config, and memory bank files.
        Score starts at 100; deductions applied for each issue found.

        Returns:
            Health report with score (0-100), grade (A-F), and recommendations

        Example:
            >>> checker = StructureHealthChecker(config)
            >>> result = checker.check_structure_health()
            >>> result.grade  # HealthGrade.A if score >= 90
            >>> result.recommendations  # List of actionable fixes
        """
        checks: list[str] = []
        issues: list[str] = []
        recommendations: list[str] = []
        score = HEALTH_INITIAL_SCORE

        score = self._check_required_directories(checks, issues, recommendations, score)
        self._check_legacy_cursor_artifacts(checks, issues, recommendations)
        score = self._check_config_file(checks, issues, recommendations, score)
        score = self._check_memory_bank_files(checks, issues, recommendations, score)

        grade, status = _determine_health_grade_and_status(score)

        return HealthCheckResult(
            score=score,
            grade=grade,
            status=status,
            checks=checks,
            issues=issues,
            recommendations=recommendations,
        )

    def _check_required_directories(
        self,
        checks_list: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
        score: int,
    ) -> int:
        """Check that all required directories exist.

        Args:
            checks_list: List of check messages to update
            issues_list: List of issue messages to update
            recommendations_list: List of recommendation messages to update
            score: Current health score

        Returns:
            Updated score after directory check
        """
        required_dirs = ["root", "memory_bank", "rules", "plans", "config"]
        missing_dirs = self._find_missing_directories(required_dirs)
        score = self._update_score_for_missing_dirs(missing_dirs, score)

        if missing_dirs:
            self._add_missing_dirs_issues(
                missing_dirs, issues_list, recommendations_list
            )
        else:
            checks_list.append("✓ All required directories exist")

        return score

    def _find_missing_directories(self, required_dirs: list[str]) -> list[str]:
        """Find missing directories from required list.

        Args:
            required_dirs: List of required directory names

        Returns:
            List of missing directory names
        """
        missing_dirs: list[str] = []
        for dir_name in required_dirs:
            path = self.config.get_path(dir_name)
            if not path.exists():
                missing_dirs.append(dir_name)
        return missing_dirs

    def _update_score_for_missing_dirs(
        self, missing_dirs: list[str], score: int
    ) -> int:
        """Update score based on number of missing directories.

        Args:
            missing_dirs: List of missing directory names
            score: Current health score

        Returns:
            Updated score
        """
        return score - (len(missing_dirs) * HEALTH_PENALTY_PER_MISSING_DIR)

    def _add_missing_dirs_issues(
        self,
        missing_dirs: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
    ) -> None:
        """Add issues and recommendations for missing directories.

        Args:
            missing_dirs: List of missing directory names
            issues_list: List of issue messages
            recommendations_list: List of recommendation messages
        """
        missing_dirs_str_list: list[str] = [str(d) for d in missing_dirs]
        issues_list.append(f"Missing directories: {', '.join(missing_dirs_str_list)}")
        recommendations_list.append(
            "Run setup_project_structure() to create missing directories"
        )

    def _check_legacy_cursor_artifacts(
        self,
        checks_list: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
    ) -> None:
        """Flag a leftover .cursor/ dir from a pre-removal Cortex version.

        Advisory only (no score penalty): startup repair removes these
        automatically, so surviving artifacts usually mean repair hasn't run
        yet, not an unhealthy structure.

        Args:
            checks_list: List of check messages to update
            issues_list: List of issue messages to update
            recommendations_list: List of recommendation messages to update
        """
        cursor_dir = get_legacy_cursor_dir_path(self.config.project_root)
        if cursor_dir.is_dir():
            issues_list.append(f"Leftover legacy .cursor/ directory: {cursor_dir}")
            recommendations_list.append(
                "Restart the Cortex MCP server to clean up leftover .cursor/ artifacts"
            )
        else:
            checks_list.append("✓ No leftover .cursor/ artifacts")

    def _check_config_file(
        self,
        checks_list: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
        score: int,
    ) -> int:
        """Check that configuration file exists and is valid.

        Args:
            checks_list: List of check messages to update
            issues_list: List of issue messages to update
            recommendations_list: List of recommendation messages to update
            score: Current health score

        Returns:
            Updated score after config file check
        """
        if not self.config.structure_config_path.exists():
            score -= HEALTH_PENALTY_NO_CONFIG
            issues_list.append("Configuration file missing")
            recommendations_list.append("Run create_structure() to generate config")
        else:
            checks_list.append("✓ Configuration file exists")

        return score

    def _check_memory_bank_files(
        self,
        checks_list: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
        score: int,
    ) -> int:
        """Check memory bank files organization.

        Args:
            checks_list: List of check messages to update
            issues_list: List of issue messages to update
            recommendations_list: List of recommendation messages to update
            score: Current health score

        Returns:
            Updated score after memory bank files check
        """
        memory_bank_dir = self.config.get_path("memory_bank")
        if memory_bank_dir.exists():
            memory_bank_files = list(memory_bank_dir.glob("*.md"))
            if len(memory_bank_files) == 0:
                score -= HEALTH_PENALTY_NO_MEMORY_BANK_FILES
                issues_list.append("No memory bank files found")
                recommendations_list.append(
                    "Add memory bank files to memory-bank directory"
                )
            else:
                checks_list.append(
                    f"✓ Found {len(memory_bank_files)} memory bank files"
                )

        return score
