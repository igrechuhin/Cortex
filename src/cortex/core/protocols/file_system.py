#!/usr/bin/env python3
"""File system and metadata protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for file system operations
and metadata index management, enabling structural subtyping for better
abstraction and reduced circular dependencies.
"""

from pathlib import Path
from typing import Protocol


class FileSystemProtocol(Protocol):
    """Protocol for file system operations using structural subtyping (PEP 544).

    This protocol defines the interface for safe file I/O operations with
    conflict detection, content hashing, and markdown parsing. Any class that
    implements these methods automatically satisfies this protocol without
    explicit inheritance.

    Used by:
        - FileSystemManager: Concrete implementation with locking and validation
        - DependencyGraph: For reading files to build dependency graphs
        - TransclusionEngine: For reading and resolving file transclusions
        - ValidationTools: For reading and validating file content

    Example implementation:
        ```python
        class CustomFileSystem:
            def validate_path(self, file_path: Path) -> bool:
                return file_path.is_relative_to(self.project_root)

            async def read_file(self, file_path: Path) -> tuple[str, str]:
                content = await aiofiles.read(file_path)
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                return (content, content_hash)

            async def write_file(
                self,
                file_path: Path,
                content: str,
                expected_hash: str | None = None,
                create_version: bool = True,
            ) -> str:
                # Validate hash, write content, return new hash
                return new_hash

            def compute_hash(self, content: str) -> str:
                return hashlib.sha256(content.encode()).hexdigest()

            def parse_sections(self, content: str) -> list[dict[str, str | int]]:
                # Parse markdown headers into sections
                return sections

            async def file_exists(self, file_path: Path) -> bool:
                return file_path.exists()

            async def cleanup_locks(self):
                # Clean up stale file locks
                pass

        # CustomFileSystem automatically satisfies FileSystemProtocol
        ```

    Note:
        - Structural subtyping means no explicit inheritance needed
        - All protocol methods must be implemented for full compatibility
        - Used throughout the system for loose coupling and testability
    """

    def validate_path(self, file_path: Path) -> bool:
        """Validate that a path is safe and within bounds.

        Args:
            file_path: Path to validate

        Returns:
            True if path is valid, False otherwise
        """
        ...

    async def read_file(self, file_path: Path) -> tuple[str, str]:
        """Read file and return content with hash.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (content, content_hash)

        Raises:
            FileNotFoundError: If file doesn't exist
            MemoryBankError: For other errors
        """
        ...

    async def write_file(
        self,
        file_path: Path,
        content: str,
        expected_hash: str | None = None,
        create_version: bool = True,
    ) -> str:
        """Write content to file with optional conflict detection.

        Args:
            file_path: Path to file
            content: Content to write
            expected_hash: Expected content hash for conflict detection
            create_version: Whether to create version snapshot

        Returns:
            New content hash

        Raises:
            ConflictError: If content hash doesn't match expected
            MemoryBankError: For other errors
        """
        ...

    def compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: Content to hash

        Returns:
            Hex digest of hash
        """
        ...

    def parse_sections(self, content: str) -> list[dict[str, str | int]]:
        """Parse markdown content into sections.

        Args:
            content: Markdown content

        Returns:
            List of section dictionaries with title, level, start_line, end_line
        """
        ...

    async def file_exists(self, file_path: Path) -> bool:
        """Check if file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists
        """
        ...

    async def cleanup_locks(self):
        """Clean up stale file locks."""
        ...


class MetadataIndexProtocol(Protocol):
    """Protocol for metadata index operations using structural subtyping (PEP 544).

    This protocol defines the interface for managing file metadata including
    token counts, hashes, sections, links, and access statistics. The metadata
    index provides fast lookups and persistence with corruption recovery. Any
    class implementing these methods automatically satisfies this protocol.

    Used by:
        - MetadataIndex: JSON-based metadata storage with corruption recovery
        - DependencyGraph: For accessing file metadata and dependencies
        - PatternAnalyzer: For analyzing file access patterns and statistics
        - QualityMetrics: For calculating quality scores based on metadata

    Example implementation:
        ```python
        class InMemoryMetadataIndex:
            def __init__(self):
                self.data = {"files": {}, "version": "1.0"}

            async def load(self) -> dict[str, object]:
                return self.data

            async def save(self):
                # Persist data to storage
                pass

            async def update_file_metadata(
                self,
                file_name: str,
                path: Path,
                exists: bool,
                size_bytes: int,
                token_count: int,
                content_hash: str,
                sections: list[dict[str, str | int]] | None = None,
                links: list[dict[str, str]] | None = None,
                transclusions: list[str] | None = None,
            ):
                self.data["files"][file_name] = {
                    "path": str(path),
                    "exists": exists,
                    "size_bytes": size_bytes,
                    "token_count": token_count,
                    "content_hash": content_hash,
                    "sections": sections or [],
                    "links": links or [],
                    "transclusions": transclusions or [],
                }

            async def get_file_metadata(self, file_name: str) -> dict[str, object] | None:
                return self.data["files"].get(file_name)

            async def get_all_files_metadata(self) -> dict[str, dict[str, object]]:
                return self.data["files"]

            async def list_all_files(self) -> list[str]:
                return list(self.data["files"].keys())

            async def increment_read_count(self, file_name: str):
                if file_name in self.data["files"]:
                    self.data["files"][file_name]["read_count"] += 1

        # InMemoryMetadataIndex automatically satisfies MetadataIndexProtocol
        ```

    Note:
        - Structural subtyping enables flexible storage backends
        - Critical for performance: metadata access is O(1) vs O(n) file reads
        - Includes corruption recovery for reliability
    """

    async def load(self) -> dict[str, object]:
        """Load metadata index from disk.

        Returns:
            Index data dictionary

        Raises:
            MemoryBankError: If load fails and recovery is not possible
        """
        ...

    async def save(self):
        """Save metadata index to disk atomically.

        Raises:
            MemoryBankError: If save fails
        """
        ...

    async def update_file_metadata(
        self,
        file_name: str,
        path: Path,
        exists: bool,
        size_bytes: int,
        token_count: int,
        content_hash: str,
        sections: list[dict[str, str | int]] | None = None,
        links: list[dict[str, str]] | None = None,
        transclusions: list[str] | None = None,
    ):
        """Update metadata for a file.

        Args:
            file_name: Name of file
            path: Full path to file
            exists: Whether file exists
            size_bytes: File size in bytes
            token_count: Number of tokens
            content_hash: SHA-256 hash of content
            sections: List of section metadata
            links: List of link metadata
            transclusions: List of transclusion targets
        """
        ...

    async def get_file_metadata(self, file_name: str) -> dict[str, object] | None:
        """Get metadata for a specific file.

        Args:
            file_name: Name of file

        Returns:
            Metadata dictionary or None if not found
        """
        ...

    async def get_all_files_metadata(self) -> dict[str, dict[str, object]]:
        """Get metadata for all files.

        Returns:
            Dictionary mapping file names to metadata
        """
        ...

    async def list_all_files(self) -> list[str]:
        """Get list of all file names in index.

        Returns:
            List of file names
        """
        ...

    async def increment_read_count(self, file_name: str):
        """Increment read count for a file.

        Args:
            file_name: Name of file
        """
        ...


__all__ = [
    "FileSystemProtocol",
    "MetadataIndexProtocol",
]
