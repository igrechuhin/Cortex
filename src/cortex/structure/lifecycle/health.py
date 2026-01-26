"""
Structure health checking for Memory Bank.

This module handles:
- Directory validation
- Symlink validation
- Configuration file validation
- Memory bank file validation
"""

from typing import Literal, cast

from cortex.core.models import ModelDict
from cortex.structure.models import HealthCheckResult
from cortex.structure.structure_config import StructureConfig


def _determine_health_grade_and_status(
    score: int,
) -> tuple[
    Literal["A", "B", "C", "D", "F"],
    Literal["healthy", "good", "fair", "warning", "critical"],
]:
    """Determine grade and status from health score.

    Args:
        score: Health score (0-100)

    Returns:
        Tuple of (grade, status)
    """
    # Use early returns to reduce nesting
    if score >= 90:
        return "A", "healthy"
    if score >= 75:
        return "B", "good"
    if score >= 60:
        return "C", "fair"
    if score >= 50:
        return "D", "warning"
    return "F", "critical"


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

        Returns:
            Health report with score and recommendations
        """
        checks: list[str] = []
        issues: list[str] = []
        recommendations: list[str] = []
        score = 100

        score = self._check_required_directories(checks, issues, recommendations, score)
        score = self._check_symlinks_validity(checks, issues, recommendations, score)
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
        return score - (len(missing_dirs) * 15)

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

    def _check_symlinks_validity(
        self,
        checks_list: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
        score: int,
    ) -> int:
        """Check that Cursor symlinks are valid.

        Args:
            checks_list: List of check messages to update
            issues_list: List of issue messages to update
            recommendations_list: List of recommendation messages to update
            score: Current health score

        Returns:
            Updated score after symlink check
        """
        symlink_location = self._get_symlink_location()
        if symlink_location:
            score = self._validate_symlinks(
                symlink_location, score, checks_list, issues_list, recommendations_list
            )

        return score

    def _get_symlink_location(self) -> str | None:
        """Get symlink location from config if cursor integration is enabled.

        Returns:
            Symlink location string or None if not enabled
        """
        cursor_integration_val = self.config.structure_config.get("cursor_integration")
        if not isinstance(cursor_integration_val, dict):
            return None

        cursor_integration = cast(ModelDict, cursor_integration_val)
        enabled_val = cursor_integration.get("enabled")
        if not isinstance(enabled_val, bool) or not enabled_val:
            return None

        symlink_location_val = cursor_integration.get("symlink_location")
        if isinstance(symlink_location_val, str):
            return symlink_location_val

        return None

    def _validate_symlinks(
        self,
        symlink_location: str,
        score: int,
        checks_list: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
    ) -> int:
        """Validate symlinks and update health lists.

        Args:
            symlink_location: Location of cursor symlinks
            score: Current health score
            checks_list: List of check messages
            issues_list: List of issue messages
            recommendations_list: List of recommendation messages

        Returns:
            Updated score
        """
        broken_symlinks = self._find_broken_symlinks(symlink_location, score)
        score = broken_symlinks[1]

        if broken_symlinks[0]:
            broken_symlinks_str_list: list[str] = [str(s) for s in broken_symlinks[0]]
            issues_list.append(
                f"Broken symlinks: {', '.join(broken_symlinks_str_list)}"
            )
            recommendations_list.append(
                "Run setup_cursor_integration() to fix symlinks"
            )
        else:
            checks_list.append("✓ All Cursor symlinks are valid")

        return score

    def _find_broken_symlinks(
        self, symlink_location: str, score: int
    ) -> tuple[list[str], int]:
        """Find broken symlinks in cursor directory.

        Args:
            symlink_location: Location of cursor symlinks
            score: Current health score

        Returns:
            Tuple of (broken_symlinks_list, updated_score)
        """
        cursor_dir = self.config.project_root / symlink_location
        broken_symlinks: list[str] = []

        for symlink_name in ["memory-bank", "rules", "plans"]:
            symlink_path = cursor_dir / symlink_name
            if symlink_path.is_symlink():
                if not symlink_path.exists():
                    broken_symlinks.append(symlink_name)
                    score -= 10

        return broken_symlinks, score

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
            score -= 10
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
                score -= 5
                issues_list.append("No memory bank files found")
                recommendations_list.append(
                    "Add memory bank files to memory-bank directory"
                )
            else:
                checks_list.append(
                    f"✓ Found {len(memory_bank_files)} memory bank files"
                )

        return score
