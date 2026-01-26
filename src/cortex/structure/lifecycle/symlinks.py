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

from cortex.core.models import JsonValue, ModelDict
from cortex.structure.models import SymlinkEntry, SymlinkReport
from cortex.structure.structure_config import StructureConfig


class CursorSymlinkManager:
    """Manages Cursor IDE symlinks for Memory Bank structure."""

    def __init__(self, config: StructureConfig):
        """Initialize symlink manager.

        Args:
            config: Structure configuration
        """
        self.config = config

    def setup_cursor_integration(self) -> SymlinkReport:
        """Setup Cursor IDE integration via symlinks.

        Returns:
            Report of created symlinks
        """
        validation_result = self._validate_cursor_integration_config(
            self.config.structure_config.get("cursor_integration")
        )
        if not validation_result["valid"]:
            return self._build_validation_error_report(validation_result)

        symlink_location = cast(str, validation_result["symlink_location"])
        symlink_config = cast(ModelDict, validation_result["symlink_config"])

        cursor_dir = self.config.project_root / symlink_location
        cursor_dir.mkdir(parents=True, exist_ok=True)

        symlinks_created: list[SymlinkEntry] = []
        errors: list[str] = []

        self._create_all_symlinks(symlink_config, cursor_dir, symlinks_created, errors)

        return SymlinkReport(
            success=True,
            symlinks_created=symlinks_created,
            errors=errors,
            platform=platform.system(),
        )

    def _build_validation_error_report(
        self, validation_result: ModelDict
    ) -> SymlinkReport:
        """Build error report from validation result."""
        error_response = validation_result.get("error_response")
        if isinstance(error_response, dict):
            error_val = error_response.get("error")
            error_msg = error_val if isinstance(error_val, str) else "Unknown error"
            return SymlinkReport(
                success=False,
                symlinks_created=[],
                errors=[error_msg],
                platform=platform.system(),
            )
        return SymlinkReport(
            success=False,
            symlinks_created=[],
            errors=["Invalid cursor integration configuration"],
            platform=platform.system(),
        )

    def create_symlink(
        self,
        target: Path,
        link: Path,
        symlinks_created: list[SymlinkEntry],
        errors: list[str],
    ) -> None:
        """Create a symlink with cross-platform compatibility.

        Args:
            target: Target path (what the symlink points to)
            link: Symlink path (the symlink itself)
            symlinks_created: List to append created symlinks to
            errors: List to append errors to
        """
        if not self._remove_existing_symlink(link, errors):
            return

        self._create_symlink_by_platform(target, link, symlinks_created, errors)

    def _remove_existing_symlink(self, link: Path, errors: list[str]) -> bool:
        """Remove existing symlink or file if it exists.

        Args:
            link: Symlink path
            errors: List of error messages to update

        Returns:
            True if successful or no removal needed, False if error occurred
        """
        if link.exists() or link.is_symlink():
            try:
                if link.is_dir() and not link.is_symlink():
                    errors.append(f"Cannot replace directory with symlink: {link}")
                    return False
                link.unlink()
            except Exception as e:
                errors.append(f"Failed to remove existing link {link}: {e}")
                return False
        return True

    def _create_symlink_by_platform(
        self,
        target: Path,
        link: Path,
        symlinks_created: list[SymlinkEntry],
        errors: list[str],
    ) -> None:
        """Create symlink with platform-specific handling.

        Args:
            target: Target path
            link: Symlink path
            symlinks_created: List to append created symlinks to
            errors: List to append errors to
        """
        try:
            rel_target = os.path.relpath(target, link.parent)

            if platform.system() == "Windows":
                self._create_windows_symlink(target, link)
            else:
                self._create_unix_symlink(rel_target, link, target)

            symlinks_created.append(
                SymlinkEntry(
                    link=str(link),
                    target=str(target),
                    relative_path=rel_target,
                )
            )
        except Exception as e:
            errors.append(f"Failed to create symlink {link} -> {target}: {e}")

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

    def _validate_cursor_integration_config(
        self,
        cursor_integration_val: JsonValue,
    ) -> ModelDict:
        """Validate cursor integration configuration."""
        if not isinstance(cursor_integration_val, dict):
            return _build_validation_error("Invalid cursor_integration config")

        cursor_integration = cast(ModelDict, cursor_integration_val)

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

        return cast(
            ModelDict,
            {
                "valid": True,
                "cursor_integration": cursor_integration,
                "symlink_location": symlink_location,
                "symlink_config": symlink_config,
            },
        )

    def _create_all_symlinks(
        self,
        symlink_config: ModelDict,
        cursor_dir: Path,
        symlinks_created: list[SymlinkEntry],
        errors: list[str],
    ) -> None:
        """Create all symlinks for cursor integration.

        Args:
            symlink_config: Symlink configuration
            cursor_dir: Cursor directory for symlinks
            symlinks_created: List to append created symlinks to
            errors: List to append errors to
        """
        if bool(symlink_config.get("memory_bank")):
            self.create_symlink(
                self.config.get_path("memory_bank"),
                cursor_dir / "memory-bank",
                symlinks_created,
                errors,
            )

        if bool(symlink_config.get("rules")):
            self.create_symlink(
                self.config.get_path("rules"),
                cursor_dir / "rules",
                symlinks_created,
                errors,
            )

        if bool(symlink_config.get("plans")):
            self.create_symlink(
                self.config.get_path("plans"),
                cursor_dir / "plans",
                symlinks_created,
                errors,
            )


def _build_validation_error(error_message: str) -> ModelDict:
    """Build validation error response."""
    return cast(
        ModelDict,
        {
            "valid": False,
            "error_response": {"success": False, "error": error_message},
        },
    )


def _validate_enabled_flag(
    cursor_integration: ModelDict,
) -> ModelDict | None:
    """Validate enabled flag."""
    enabled_val = cursor_integration.get("enabled")
    if not isinstance(enabled_val, bool) or not enabled_val:
        return _build_validation_error("Cursor integration is disabled")
    return None


def _validate_symlink_location(
    cursor_integration: ModelDict,
) -> tuple[ModelDict | None, str]:
    """Validate symlink location."""
    symlink_location_val = cursor_integration.get("symlink_location")
    if not isinstance(symlink_location_val, str):
        return (
            _build_validation_error("Invalid symlink_location config"),
            "",
        )
    return None, symlink_location_val


def _validate_symlinks(
    cursor_integration: ModelDict,
) -> tuple[ModelDict | None, ModelDict]:
    """Validate symlinks config."""
    symlinks_val = cursor_integration.get("symlinks")
    if not isinstance(symlinks_val, dict):
        return _build_validation_error("Invalid symlinks config"), {}
    return None, cast(ModelDict, symlinks_val)
