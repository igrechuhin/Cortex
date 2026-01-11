"""
Structure health checking for Memory Bank.

This module handles:
- Directory validation
- Symlink validation
- Configuration file validation
- Memory bank file validation
"""

from typing import cast

from cortex.structure.structure_config import StructureConfig


def _determine_health_grade_and_status(
    score: int,
) -> tuple[str, str]:
    """Determine grade and status from health score.

    Args:
        score: Health score (0-100)

    Returns:
        Tuple of (grade, status)
    """
    if score >= 90:
        return "A", "healthy"
    elif score >= 75:
        return "B", "good"
    elif score >= 60:
        return "C", "fair"
    elif score >= 50:
        return "D", "warning"
    else:
        return "F", "critical"


class StructureHealthChecker:
    """Checks health of Memory Bank structure."""

    def __init__(self, config: StructureConfig):
        """Initialize health checker.

        Args:
            config: Structure configuration
        """
        self.config = config

    def check_structure_health(self) -> dict[str, object]:
        """Check the health of the project structure.

        Returns:
            Health report with score and recommendations
        """
        health: dict[str, object] = {
            "score": 100,
            "grade": "A",
            "status": "healthy",
            "checks": [],
            "issues": [],
            "recommendations": [],
        }

        score = self._check_required_directories(health)
        score = self._check_symlinks_validity(health, score)
        score = self._check_config_file(health, score)
        score = self._check_memory_bank_files(health, score)

        health["score"] = score
        grade, status = _determine_health_grade_and_status(score)
        health["grade"] = grade
        health["status"] = status

        return health

    def _extract_health_lists(
        self, health: dict[str, object]
    ) -> tuple[list[str], list[str], list[str], int]:
        """Extract typed lists from health dictionary.

        Args:
            health: Health report dictionary

        Returns:
            Tuple of (checks_list, issues_list, recommendations_list, score)
        """
        score_val = health.get("score", 100)
        score = int(score_val) if isinstance(score_val, (int, float)) else 100

        checks_val = health.get("checks", [])
        checks_list: list[str] = (
            cast(list[str], checks_val) if isinstance(checks_val, list) else []
        )

        issues_val = health.get("issues", [])
        issues_list: list[str] = (
            cast(list[str], issues_val) if isinstance(issues_val, list) else []
        )

        recommendations_val = health.get("recommendations", [])
        recommendations_list: list[str] = (
            cast(list[str], recommendations_val)
            if isinstance(recommendations_val, list)
            else []
        )

        return checks_list, issues_list, recommendations_list, score

    def _update_health_dict(
        self,
        health: dict[str, object],
        checks_list: list[str],
        issues_list: list[str],
        recommendations_list: list[str],
    ) -> None:
        """Update health dictionary with typed lists.

        Args:
            health: Health report dictionary to update
            checks_list: List of check messages
            issues_list: List of issue messages
            recommendations_list: List of recommendation messages
        """
        health["checks"] = checks_list
        health["issues"] = issues_list
        health["recommendations"] = recommendations_list

    def _check_required_directories(self, health: dict[str, object]) -> int:
        """Check that all required directories exist.

        Args:
            health: Health report dictionary to update

        Returns:
            Updated score after directory check
        """
        checks_list, issues_list, recommendations_list, score = (
            self._extract_health_lists(health)
        )

        required_dirs = ["root", "memory_bank", "rules", "plans", "config"]
        missing_dirs = self._find_missing_directories(required_dirs)
        score = self._update_score_for_missing_dirs(missing_dirs, score)

        if missing_dirs:
            self._add_missing_dirs_issues(
                missing_dirs, issues_list, recommendations_list
            )
        else:
            checks_list.append("✓ All required directories exist")

        self._update_health_dict(health, checks_list, issues_list, recommendations_list)

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

    def _check_symlinks_validity(self, health: dict[str, object], score: int) -> int:
        """Check that Cursor symlinks are valid.

        Args:
            health: Health report dictionary to update
            score: Current health score

        Returns:
            Updated score after symlink check
        """
        checks_list, issues_list, recommendations_list, _ = self._extract_health_lists(
            health
        )

        symlink_location = self._get_symlink_location()
        if symlink_location:
            score = self._validate_symlinks(
                symlink_location, score, checks_list, issues_list, recommendations_list
            )

        self._update_health_dict(health, checks_list, issues_list, recommendations_list)

        return score

    def _get_symlink_location(self) -> str | None:
        """Get symlink location from config if cursor integration is enabled.

        Returns:
            Symlink location string or None if not enabled
        """
        cursor_integration_val = self.config.structure_config.get("cursor_integration")
        if not isinstance(cursor_integration_val, dict):
            return None

        cursor_integration = cast(dict[str, object], cursor_integration_val)
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

    def _check_config_file(self, health: dict[str, object], score: int) -> int:
        """Check that configuration file exists and is valid.

        Args:
            health: Health report dictionary to update
            score: Current health score

        Returns:
            Updated score after config file check
        """
        checks_list, issues_list, recommendations_list, _ = self._extract_health_lists(
            health
        )

        if not self.config.structure_config_path.exists():
            score -= 10
            issues_list.append("Configuration file missing")
            recommendations_list.append("Run create_structure() to generate config")
        else:
            checks_list.append("✓ Configuration file exists")

        self._update_health_dict(health, checks_list, issues_list, recommendations_list)

        return score

    def _check_memory_bank_files(self, health: dict[str, object], score: int) -> int:
        """Check memory bank files organization.

        Args:
            health: Health report dictionary to update
            score: Current health score

        Returns:
            Updated score after memory bank files check
        """
        checks_list, issues_list, recommendations_list, _ = self._extract_health_lists(
            health
        )

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

        self._update_health_dict(health, checks_list, issues_list, recommendations_list)

        return score
