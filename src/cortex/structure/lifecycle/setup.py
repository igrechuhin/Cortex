"""
Structure setup operations for Memory Bank.

This module handles:
- Directory creation
- Configuration file generation
- README file generation
"""

from pathlib import Path
from typing import cast

from cortex.structure.structure_config import StructureConfig
from cortex.structure.structure_templates import (
    generate_memory_bank_readme,
    generate_plans_readme,
    generate_rules_readme,
)


class StructureSetup:
    """Handles setup operations for Memory Bank structure."""

    def __init__(self, config: StructureConfig):
        """Initialize structure setup.

        Args:
            config: Structure configuration
        """
        self.config = config

    async def create_structure(self, force: bool = False) -> dict[str, object]:
        """Create the complete standardized structure.

        Args:
            force: Force recreation even if structure exists

        Returns:
            Report of created directories and files
        """
        report: dict[str, object] = {
            "created_directories": [],
            "created_files": [],
            "skipped": [],
            "errors": [],
        }

        self._create_required_directories(report, force)
        await self._create_config_file(report)
        self._create_readme_files(report, force)

        return report

    def _get_required_directory_list(self) -> list[Path]:
        """Get list of all required directories."""
        return [
            self.config.get_path("root"),
            self.config.get_path("memory_bank"),
            self.config.get_path("rules"),
            self.config.get_path("rules") / "local",
            self.config.get_path("plans"),
            self.config.get_path("plans") / "templates",
            self.config.get_path("plans") / "active",
            self.config.get_path("plans") / "completed",
            self.config.get_path("plans") / "archived",
            self.config.get_path("config"),
            self.config.get_path("archived"),
        ]

    def _extract_report_lists(
        self, report: dict[str, object]
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract and type-cast report lists."""
        skipped_val = report.get("skipped", [])
        created_dirs_val = report.get("created_directories", [])
        errors_val = report.get("errors", [])

        skipped_list: list[str] = (
            cast(list[str], skipped_val) if isinstance(skipped_val, list) else []
        )
        created_dirs_list: list[str] = (
            cast(list[str], created_dirs_val)
            if isinstance(created_dirs_val, list)
            else []
        )
        errors_list: list[str] = (
            cast(list[str], errors_val) if isinstance(errors_val, list) else []
        )

        return skipped_list, created_dirs_list, errors_list

    def _process_directory_creation(
        self,
        directory: Path,
        force: bool,
        skipped_list: list[str],
        created_dirs_list: list[str],
        errors_list: list[str],
    ) -> None:
        """Process creation of a single directory."""
        if directory.exists() and not force:
            skipped_list.append(str(directory))
        else:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                created_dirs_list.append(str(directory))
            except Exception as e:
                errors_list.append(f"Failed to create {directory}: {e}")

    def _create_required_directories(
        self, report: dict[str, object], force: bool
    ) -> None:
        """Create all required directories for the structure.

        Args:
            report: Report dictionary to update
            force: Force recreation even if directories exist
        """
        directories = self._get_required_directory_list()
        skipped_list, created_dirs_list, errors_list = self._extract_report_lists(
            report
        )

        for directory in directories:
            self._process_directory_creation(
                directory, force, skipped_list, created_dirs_list, errors_list
            )

        report["skipped"] = skipped_list
        report["created_directories"] = created_dirs_list
        report["errors"] = errors_list

    async def _create_config_file(self, report: dict[str, object]) -> None:
        """Create structure configuration file.

        Args:
            report: Report dictionary to update
        """
        created_files_val = report.get("created_files", [])
        created_files_list: list[str] = (
            cast(list[str], created_files_val)
            if isinstance(created_files_val, list)
            else []
        )
        errors_val = report.get("errors", [])
        errors_list: list[str] = (
            cast(list[str], errors_val) if isinstance(errors_val, list) else []
        )

        try:
            await self.config.save_structure_config()
            created_files_list.append(str(self.config.structure_config_path))
        except Exception as e:
            errors_list.append(f"Failed to create config: {e}")

        report["created_files"] = created_files_list
        report["errors"] = errors_list

    def _create_readme_files(self, report: dict[str, object], force: bool) -> None:
        """Create README files for structure directories.

        Args:
            report: Report dictionary to update
            force: Force recreation even if files exist
        """
        created_files_val = report.get("created_files", [])
        created_files_list: list[str] = (
            cast(list[str], created_files_val)
            if isinstance(created_files_val, list)
            else []
        )
        errors_val = report.get("errors", [])
        errors_list: list[str] = (
            cast(list[str], errors_val) if isinstance(errors_val, list) else []
        )

        readme_files = [
            (self.config.get_path("plans") / "README.md", generate_plans_readme()),
            (
                self.config.get_path("memory_bank") / "README.md",
                generate_memory_bank_readme(),
            ),
            (self.config.get_path("rules") / "README.md", generate_rules_readme()),
        ]

        for readme_path, content in readme_files:
            if not readme_path.exists() or force:
                try:
                    _ = readme_path.write_text(content, encoding="utf-8")
                    created_files_list.append(str(readme_path))
                except Exception as e:
                    errors_list.append(f"Failed to create {readme_path}: {e}")

        report["created_files"] = created_files_list
        report["errors"] = errors_list
