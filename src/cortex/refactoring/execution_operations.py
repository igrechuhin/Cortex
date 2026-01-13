"""Execution Operations - Execute individual refactoring operations.

This module contains the execution logic for different types of refactoring operations.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from cortex.core.exceptions import ValidationError
from cortex.core.file_system import FileSystemManager

from .execution_validator import RefactoringOperation


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
            str, Callable[[RefactoringOperation], Awaitable[None]]
        ] = {
            "consolidate": self.execute_consolidation,
            "split": self.execute_split,
            "move": self._execute_move,
            "rename": self._execute_rename,
            "create": self.execute_create,
            "delete": self._execute_delete,
            "modify": self._execute_modify,
        }

    async def execute_operation(self, operation: RefactoringOperation) -> None:
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

    async def execute_consolidation(self, operation: RefactoringOperation) -> None:
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
        self, operation: RefactoringOperation
    ) -> tuple[str, list[str], list[dict[str, object]]]:
        """Validate and extract consolidation parameters."""
        extraction_target_raw = operation.parameters.get("extraction_target")
        if not isinstance(extraction_target_raw, str):
            raise ValidationError("extraction_target must be a string")
        extraction_target: str = extraction_target_raw

        files_raw = operation.parameters.get("files", [])
        if not isinstance(files_raw, list):
            raise ValidationError("files must be a list")
        files_list: list[object] = cast(list[object], files_raw)
        files: list[str] = [str(f) for f in files_list if isinstance(f, str)]

        sections_raw = operation.parameters.get("sections", [])
        if not isinstance(sections_raw, list):
            raise ValidationError("sections must be a list")
        sections_list: list[object] = cast(list[object], sections_raw)
        sections: list[dict[str, object]] = [
            cast(dict[str, object], s) for s in sections_list if isinstance(s, dict)
        ]

        return extraction_target, files, sections

    def _build_consolidated_content(
        self, extraction_target: str, sections: list[dict[str, object]]
    ) -> str:
        """Build consolidated content from sections."""
        consolidated_content = f"# {extraction_target}\n\n"
        for section in sections:
            content_raw = section.get("content", "")
            content_str = str(content_raw) if content_raw is not None else ""
            consolidated_content += f"{content_str}\n\n"
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
        sections: list[dict[str, object]],
    ) -> None:
        """Update source files to use transclusion syntax."""
        for file_path in files:
            full_path = self.memory_bank_dir / file_path
            if not full_path.exists():
                continue

            content_tuple = await self.fs_manager.read_file(full_path)
            content, _ = content_tuple

            parsed_sections = self.fs_manager.parse_sections(content)

            for section in sections:
                section_file = section.get("file")
                if section_file != file_path:
                    continue

                section_title_raw = section.get("section", "")
                section_title = (
                    str(section_title_raw) if section_title_raw is not None else ""
                )
                transclusion = f"{{{{include: {extraction_target}#{section_title}}}}}"

                content = self._replace_section_with_transclusion(
                    content, parsed_sections, section_title, transclusion
                )

            _ = await self.fs_manager.write_file(full_path, content)

    def _replace_section_with_transclusion(
        self,
        content: str,
        parsed_sections: list[dict[str, str | int]],
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
            heading = str(section.get("heading", ""))
            heading_title = heading.lstrip("#").strip()

            if heading_title == section_title:
                line_start = int(section.get("line_start", 0))
                line_end = int(section.get("line_end", 0))

                if line_start > 0 and line_end > line_start:
                    before = lines[:line_start]
                    replacement = [lines[line_start - 1], "", transclusion, ""]
                    after = lines[line_end:] if line_end < len(lines) else []

                    lines = before + replacement + after
                    break

        return "\n".join(lines)

    async def execute_split(self, operation: RefactoringOperation) -> None:
        """Execute file split."""
        original_file = self.memory_bank_dir / operation.target_file
        new_file_name_raw = operation.parameters.get("new_file")
        if not isinstance(new_file_name_raw, str):
            raise ValidationError("new_file parameter must be a string")
        new_file_name: str = new_file_name_raw

        sections_raw = operation.parameters.get("sections", [])
        if not isinstance(sections_raw, list):
            sections: list[str] = []
        else:
            sections_list: list[object] = cast(list[object], sections_raw)
            sections = [
                str(s) for s in sections_list if isinstance(s, (str, int, float))
            ]
        content_raw = operation.parameters.get("content", "")
        content = str(content_raw) if content_raw is not None else ""

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
        parsed_sections: list[dict[str, str | int]],
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
            heading = str(section.get("heading", ""))
            heading_title = heading.lstrip("#").strip()

            if heading_title not in section_titles:
                continue

            line_start = int(section.get("line_start", 0))
            line_end = int(section.get("line_end", 0))

            if line_start <= 0 or line_end < line_start:
                continue

            for line_num in range(line_start - 1, line_end):
                lines_to_remove.add(line_num)

        remaining_lines = [
            line for i, line in enumerate(lines) if i not in lines_to_remove
        ]

        return "\n".join(remaining_lines)

    async def _execute_move(self, operation: RefactoringOperation) -> None:
        """Execute file move."""
        source = self.memory_bank_dir / operation.target_file
        destination_raw = operation.parameters.get("destination")
        if not isinstance(destination_raw, str):
            raise ValidationError("destination parameter must be a string")
        destination: Path = self.memory_bank_dir / destination_raw

        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            _ = source.rename(destination)

    async def _execute_rename(self, operation: RefactoringOperation) -> None:
        """Execute file rename."""
        old_path = self.memory_bank_dir / operation.target_file
        new_name_raw = operation.parameters.get("new_name")
        if not isinstance(new_name_raw, str):
            raise ValidationError("new_name parameter must be a string")
        new_name: str = new_name_raw
        new_path: Path = old_path.parent / new_name

        if old_path.exists():
            _ = old_path.rename(new_path)

    async def execute_create(self, operation: RefactoringOperation) -> None:
        """Execute file/directory creation."""
        target = self.memory_bank_dir / operation.target_file

        if operation.parameters.get("type") == "directory":
            target.mkdir(parents=True, exist_ok=True)
        else:
            content_raw = operation.parameters.get("content", "")
            content = str(content_raw) if content_raw is not None else ""
            _ = await self.fs_manager.write_file(target, content)

    async def _execute_delete(self, operation: RefactoringOperation) -> None:
        """Execute file deletion."""
        target = self.memory_bank_dir / operation.target_file

        if target.exists():
            if target.is_file():
                target.unlink()
            else:
                import shutil

                shutil.rmtree(target)

    async def _execute_modify(self, operation: RefactoringOperation) -> None:
        """Execute file modification."""
        target = self.memory_bank_dir / operation.target_file
        content_raw = operation.parameters.get("content", "")
        content = str(content_raw) if content_raw is not None else ""

        _ = await self.fs_manager.write_file(target, content)
