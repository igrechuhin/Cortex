"""
Cursor IDE symlink management for Memory Bank structure.

This module handles:
- Symlink creation and validation
- Cross-platform symlink support (Unix/macOS/Windows)
- Cursor IDE integration
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import cast

from cortex.structure.structure_config import StructureConfig


class CursorSymlinkManager:
    """Manages Cursor IDE symlinks for Memory Bank structure."""

    def __init__(self, config: StructureConfig):
        """Initialize symlink manager.

        Args:
            config: Structure configuration
        """
        self.config = config

    def setup_cursor_integration(self) -> dict[str, object]:
        """Setup Cursor IDE integration via symlinks.

        Returns:
            Report of created symlinks
        """
        validation_result = self._validate_cursor_integration_config(
            self.config.structure_config.get("cursor_integration")
        )
        if not validation_result["valid"]:
            return cast(dict[str, object], validation_result.get("error_response", {}))

        symlink_location = cast(str, validation_result["symlink_location"])
        symlink_config = cast(dict[str, object], validation_result["symlink_config"])

        cursor_dir = self.config.project_root / symlink_location
        cursor_dir.mkdir(parents=True, exist_ok=True)

        report: dict[str, object] = {
            "success": True,
            "symlinks_created": [],
            "errors": [],
            "platform": platform.system(),
        }

        self._create_all_symlinks(symlink_config, cursor_dir, report)

        return report

    def create_symlink(
        self, target: Path, link: Path, report: dict[str, object]
    ) -> None:
        """Create a symlink with cross-platform compatibility.

        Args:
            target: Target path (what the symlink points to)
            link: Symlink path (the symlink itself)
            report: Report dictionary to update
        """
        errors_list, symlinks_list = self._extract_symlink_report_lists(report)

        if not self._remove_existing_symlink(link, errors_list, report):
            return

        self._create_symlink_by_platform(target, link, errors_list, symlinks_list)
        self._update_symlink_report(report, errors_list, symlinks_list)

    def _extract_symlink_report_lists(
        self, report: dict[str, object]
    ) -> tuple[list[str], list[dict[str, object]]]:
        """Extract typed lists from symlink report.

        Args:
            report: Report dictionary

        Returns:
            Tuple of (errors_list, symlinks_list)
        """
        errors_val = report.get("errors", [])
        errors_list: list[str] = (
            cast(list[str], errors_val) if isinstance(errors_val, list) else []
        )
        symlinks_created_val = report.get("symlinks_created", [])
        symlinks_list: list[dict[str, object]] = (
            cast(list[dict[str, object]], symlinks_created_val)
            if isinstance(symlinks_created_val, list)
            else []
        )
        return errors_list, symlinks_list

    def _remove_existing_symlink(
        self, link: Path, errors_list: list[str], report: dict[str, object]
    ) -> bool:
        """Remove existing symlink or file if it exists.

        Args:
            link: Symlink path
            errors_list: List of error messages
            report: Report dictionary to update

        Returns:
            True if successful or no removal needed, False if error occurred
        """
        if link.exists() or link.is_symlink():
            try:
                if link.is_dir() and not link.is_symlink():
                    errors_list.append(f"Cannot replace directory with symlink: {link}")
                    report["errors"] = errors_list
                    return False
                link.unlink()
            except Exception as e:
                errors_list.append(f"Failed to remove existing link {link}: {e}")
                report["errors"] = errors_list
                return False
        return True

    def _create_symlink_by_platform(
        self,
        target: Path,
        link: Path,
        errors_list: list[str],
        symlinks_list: list[dict[str, object]],
    ) -> None:
        """Create symlink with platform-specific handling.

        Args:
            target: Target path
            link: Symlink path
            errors_list: List of error messages
            symlinks_list: List of created symlinks
        """
        try:
            rel_target = os.path.relpath(target, link.parent)

            if platform.system() == "Windows":
                self._create_windows_symlink(target, link)
            else:
                self._create_unix_symlink(rel_target, link, target)

            symlinks_list.append(
                {"link": str(link), "target": str(target), "relative_path": rel_target}
            )
        except Exception as e:
            errors_list.append(f"Failed to create symlink {link} -> {target}: {e}")

    def _create_windows_symlink(self, target: Path, link: Path) -> None:
        """Create symlink on Windows platform.

        Args:
            target: Target path
            link: Symlink path
        """
        if target.is_dir():
            _ = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                check=True,
                capture_output=True,
            )
        else:
            _ = subprocess.run(
                ["cmd", "/c", "mklink", str(link), str(target)],
                check=True,
                capture_output=True,
            )

    def _create_unix_symlink(self, rel_target: str, link: Path, target: Path) -> None:
        """Create symlink on Unix/macOS platform.

        Args:
            rel_target: Relative path to target
            link: Symlink path
            target: Target path
        """
        os.symlink(rel_target, link, target_is_directory=target.is_dir())

    def _update_symlink_report(
        self,
        report: dict[str, object],
        errors_list: list[str],
        symlinks_list: list[dict[str, object]],
    ) -> None:
        """Update report with symlink creation results.

        Args:
            report: Report dictionary to update
            errors_list: List of error messages
            symlinks_list: List of created symlinks
        """
        report["symlinks_created"] = symlinks_list
        report["errors"] = errors_list

    def _validate_cursor_integration_config(
        self,
        cursor_integration_val: object,
    ) -> dict[str, object]:
        """Validate cursor integration configuration."""
        if not isinstance(cursor_integration_val, dict):
            return _build_validation_error("Invalid cursor_integration config")

        cursor_integration = cast(dict[str, object], cursor_integration_val)

        enabled_error = _validate_enabled_flag(cursor_integration)
        if enabled_error:
            return enabled_error

        symlink_location_error, symlink_location = _validate_symlink_location(
            cursor_integration
        )
        if symlink_location_error:
            return symlink_location_error

        symlinks_error, symlink_config = _validate_symlinks(cursor_integration)
        if symlinks_error:
            return symlinks_error

        return {
            "valid": True,
            "cursor_integration": cursor_integration,
            "symlink_location": symlink_location,
            "symlink_config": symlink_config,
        }

    def _create_all_symlinks(
        self,
        symlink_config: dict[str, object],
        cursor_dir: Path,
        report: dict[str, object],
    ) -> None:
        """Create all symlinks for cursor integration."""
        if symlink_config.get("knowledge"):
            self.create_symlink(
                self.config.get_path("knowledge"), cursor_dir / "knowledge", report
            )

        if symlink_config.get("rules"):
            self.create_symlink(
                self.config.get_path("rules"), cursor_dir / "rules", report
            )

        if symlink_config.get("plans"):
            self.create_symlink(
                self.config.get_path("plans"), cursor_dir / "plans", report
            )

        if symlink_config.get("cursorrules_main"):
            main_cursorrules = (
                self.config.get_path("rules") / "local" / "main.cursorrules"
            )
            if main_cursorrules.exists():
                self.create_symlink(
                    main_cursorrules, cursor_dir.parent / ".cursorrules", report
                )


def _build_validation_error(error_message: str) -> dict[str, object]:
    """Build validation error response."""
    return {
        "valid": False,
        "error_response": {"success": False, "error": error_message},
    }


def _validate_enabled_flag(
    cursor_integration: dict[str, object],
) -> dict[str, object] | None:
    """Validate enabled flag."""
    enabled_val = cursor_integration.get("enabled")
    if not isinstance(enabled_val, bool) or not enabled_val:
        return _build_validation_error("Cursor integration is disabled")
    return None


def _validate_symlink_location(
    cursor_integration: dict[str, object],
) -> tuple[dict[str, object] | None, str]:
    """Validate symlink location."""
    symlink_location_val = cursor_integration.get("symlink_location")
    if not isinstance(symlink_location_val, str):
        return (
            _build_validation_error("Invalid symlink_location config"),
            "",
        )
    return None, symlink_location_val


def _validate_symlinks(
    cursor_integration: dict[str, object],
) -> tuple[dict[str, object] | None, dict[str, object]]:
    """Validate symlinks config."""
    symlinks_val = cursor_integration.get("symlinks")
    if not isinstance(symlinks_val, dict):
        return (
            _build_validation_error("Invalid symlinks config"),
            {},
        )
    return None, cast(dict[str, object], symlinks_val)
