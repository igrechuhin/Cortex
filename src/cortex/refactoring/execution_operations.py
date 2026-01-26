"""Execution Operations - Execute individual refactoring operations.

This module contains the execution logic for different types of refactoring operations.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path

from cortex.core.exceptions import ValidationError
from cortex.core.file_system import FileSystemManager
from cortex.core.models import SectionMetadata

from .models import RefactoringOperationModel


class ExecutionOperations:
    """Execute individual refactoring operations."""

    def __init__(
        self,
        memory_bank_dir: Path,
        fs_manager: FileSystemManager,
    ) -> None:
        """
        Initialize execution operations.

        Args:
            memory_bank_dir: Memory bank directory path
            fs_manager: File system manager instance
        """
        self.memory_bank_dir: Path = memory_bank_dir
        self.fs_manager: FileSystemManager = fs_manager

        # Operation dispatch table for reduced complexity
        self._operation_handlers: dict[
            str, Callable[[RefactoringOperationModel], Awaitable[None]]
        ] = {
            "consolidate": self.execute_consolidation,
            "split": self.execute_split,
            "move": self._execute_move,
            "rename": self._execute_rename,
            "create": self.execute_create,
            "delete": self._execute_delete,
            "modify": self._execute_modify,
        }

    async def execute_operation(self, operation: RefactoringOperationModel) -> None:
        """Execute a single refactoring operation.

        Uses dispatch table to route to appropriate handler based on operation type.

        Args:
            operation: Refactoring operation to execute

        Raises:
            ValidationError: If operation type is unknown
        """
        handler = self._operation_handlers.get(operation.operation_type)

        if handler is None:
            raise ValidationError(
                "Unknown operation type: "
                + f"{operation.operation_type}. Valid types: "
                + f"{list(self._operation_handlers.keys())}"
            )

        await handler(operation)

    async def execute_consolidation(self, operation: RefactoringOperationModel) -> None:
        """Execute content consolidation."""
        extraction_target, files, sections = self._validate_consolidation_params(
            operation
        )
        consolidated_content = self._build_consolidated_content(
            extraction_target, sections
        )
        await self._write_consolidated_file(extraction_target, consolidated_content)
        await self._update_source_files_with_transclusions(
            extraction_target, files, sections
        )

    def _validate_consolidation_params(
        self, operation: RefactoringOperationModel
    ) -> tuple[str, list[str], list[str]]:
        """Validate and extract consolidation parameters."""
        extraction_target = operation.parameters.destination_file or ""

        files = []
        if operation.parameters.source_file:
            files = [operation.parameters.source_file]

        sections = []
        if operation.parameters.sections:
            sections = operation.parameters.sections

        return extraction_target, files, sections

    def _build_consolidated_content(
        self, extraction_target: str, sections: list[str]
    ) -> str:
        """Build consolidated content from sections."""
        consolidated_content = f"# {extraction_target}\n\n"
        # Sections are now just section names, not dicts with content
        # Content will be extracted from files during execution
        for section in sections:
            consolidated_content += f"## {section}\n\n"
        return consolidated_content

    async def _write_consolidated_file(
        self, extraction_target: str, content: str
    ) -> None:
        """Write consolidated content to target file."""
        target_path = self.memory_bank_dir / extraction_target
        _ = await self.fs_manager.write_file(target_path, content)

    async def _update_source_files_with_transclusions(
        self,
        extraction_target: str,
        files: list[str],
        sections: list[str],
    ) -> None:
        """Update source files to use transclusion syntax."""
        for file_path in files:
            full_path = self.memory_bank_dir / file_path
            if not full_path.exists():
                continue

            content_tuple = await self.fs_manager.read_file(full_path)
            content, _ = content_tuple

            parsed_sections = self.fs_manager.parse_sections(content)

            for section_title in sections:
                # For consolidation, sections are just section names
                # All sections in the list belong to the current file
                transclusion = f"{{{{include: {extraction_target}#{section_title}}}}}"

                content = self._replace_section_with_transclusion(
                    content, parsed_sections, section_title, transclusion
                )

            _ = await self.fs_manager.write_file(full_path, content)

    def _replace_section_with_transclusion(
        self,
        content: str,
        parsed_sections: list[SectionMetadata],
        section_title: str,
        transclusion: str,
    ) -> str:
        """Replace a section's content with transclusion syntax.

        Args:
            content: The full file content
            parsed_sections: List of parsed sections from FileSystemManager
            section_title: Title of section to replace
            transclusion: Transclusion syntax to insert

        Returns:
            Updated content with section replaced by transclusion
        """
        lines = content.split("\n")

        for section in parsed_sections:
            heading_title = section.title.lstrip("#").strip()

            if heading_title == section_title:
                line_start = section.line_start
                line_end = section.line_end

                if line_start > 0 and line_end > line_start:
                    before = lines[: line_start - 1]
                    replacement = [lines[line_start - 1], "", transclusion, ""]
                    after = lines[line_end:] if line_end < len(lines) else []

                    lines = before + replacement + after
                    break

        return "\n".join(lines)

    async def execute_split(self, operation: RefactoringOperationModel) -> None:
        """Execute file split."""
        original_file = self.memory_bank_dir / operation.target_file
        new_file_name = operation.parameters.destination_file or ""
        if not new_file_name:
            raise ValidationError("destination_file parameter must be provided")

        sections = operation.parameters.sections or []
        content = operation.parameters.content or ""

        new_file_path = self.memory_bank_dir / new_file_name
        _ = await self.fs_manager.write_file(new_file_path, content)

        if original_file.exists():
            original_content_tuple = await self.fs_manager.read_file(original_file)
            original_content_str = original_content_tuple[0]

            parsed_sections = self.fs_manager.parse_sections(original_content_str)

            updated_content = self._remove_sections(
                original_content_str, parsed_sections, sections
            )

            _ = await self.fs_manager.write_file(original_file, updated_content)

    def _remove_sections(
        self,
        content: str,
        parsed_sections: list[SectionMetadata],
        section_titles: list[str],
    ) -> str:
        """Remove specified sections from content.

        Args:
            content: The full file content
            parsed_sections: List of parsed sections from FileSystemManager
            section_titles: List of section titles to remove

        Returns:
            Updated content with sections removed
        """
        lines = content.split("\n")
        lines_to_remove: set[int] = set()

        for section in parsed_sections:
            heading_title = section.title.lstrip("#").strip()

            if heading_title not in section_titles:
                continue

            line_start = section.line_start
            line_end = section.line_end

            if line_start <= 0 or line_end < line_start:
                continue

            for line_num in range(line_start - 1, line_end):
                lines_to_remove.add(line_num)

        remaining_lines = [
            line for i, line in enumerate(lines) if i not in lines_to_remove
        ]

        return "\n".join(remaining_lines)

    async def _execute_move(self, operation: RefactoringOperationModel) -> None:
        """Execute file move."""
        source = self.memory_bank_dir / operation.target_file
        destination_file = operation.parameters.destination_file
        if not destination_file:
            raise ValidationError("destination_file parameter must be provided")
        destination: Path = self.memory_bank_dir / destination_file

        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            _ = source.rename(destination)

    async def _execute_rename(self, operation: RefactoringOperationModel) -> None:
        """Execute file rename."""
        old_path = self.memory_bank_dir / operation.target_file
        new_name = operation.parameters.new_name
        if not new_name:
            raise ValidationError("new_name parameter must be provided")
        new_path: Path = old_path.parent / new_name

        if old_path.exists():
            _ = old_path.rename(new_path)

    async def execute_create(self, operation: RefactoringOperationModel) -> None:
        """Execute file/directory creation."""
        target = self.memory_bank_dir / operation.target_file

        if operation.parameters.is_directory:
            target.mkdir(parents=True, exist_ok=True)
        else:
            content = operation.parameters.content or ""
            _ = await self.fs_manager.write_file(target, content)

    async def _execute_delete(self, operation: RefactoringOperationModel) -> None:
        """Execute file deletion."""
        target = self.memory_bank_dir / operation.target_file

        if target.exists():
            if target.is_file():
                target.unlink()
            else:
                import shutil

                shutil.rmtree(target)

    async def _execute_modify(self, operation: RefactoringOperationModel) -> None:
        """Execute file modification."""
        target = self.memory_bank_dir / operation.target_file
        content = operation.parameters.content or ""
        _ = await self.fs_manager.write_file(target, content)
