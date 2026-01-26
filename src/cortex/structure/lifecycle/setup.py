"""
Structure setup operations for Memory Bank.

This module handles:
- Directory creation
- Configuration file generation
- README file generation
"""

from pathlib import Path

from cortex.structure.models import SetupReport
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

    async def create_structure(self, force: bool = False) -> SetupReport:
        """Create the complete standardized structure.

        Args:
            force: Force recreation even if structure exists

        Returns:
            Report of created directories and files
        """
        created_directories: list[str] = []
        created_files: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []

        self._create_required_directories(created_directories, skipped, errors, force)
        await self._create_config_file(created_files, errors)
        self._create_readme_files(created_files, errors, force)

        return SetupReport(
            created_directories=created_directories,
            created_files=created_files,
            skipped=skipped,
            errors=errors,
        )

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
        self,
        created_directories: list[str],
        skipped: list[str],
        errors: list[str],
        force: bool,
    ) -> None:
        """Create all required directories for the structure.

        Args:
            created_directories: List to append created directories to
            skipped: List to append skipped directories to
            errors: List to append errors to
            force: Force recreation even if directories exist
        """
        directories = self._get_required_directory_list()

        for directory in directories:
            self._process_directory_creation(
                directory, force, skipped, created_directories, errors
            )

    async def _create_config_file(
        self, created_files: list[str], errors: list[str]
    ) -> None:
        """Create structure configuration file.

        Args:
            created_files: List to append created files to
            errors: List to append errors to
        """
        try:
            await self.config.save_structure_config()
            created_files.append(str(self.config.structure_config_path))
        except Exception as e:
            errors.append(f"Failed to create config: {e}")

    def _create_readme_files(
        self, created_files: list[str], errors: list[str], force: bool
    ) -> None:
        """Create README files for structure directories.

        Args:
            created_files: List to append created files to
            errors: List to append errors to
            force: Force recreation even if files exist
        """
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
                    created_files.append(str(readme_path))
                except Exception as e:
                    errors.append(f"Failed to create {readme_path}: {e}")
