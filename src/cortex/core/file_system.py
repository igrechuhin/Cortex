"""File system operations with locking, conflict detection, and markdown parsing."""

import asyncio
import hashlib
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from cortex.core.constants import (
    LOCK_POLL_INTERVAL_SECONDS,
    RATE_LIMIT_OPS_PER_SECOND,
)

from .async_file_utils import open_async_text_file
from .exceptions import FileConflictError, FileLockTimeoutError, GitConflictError
from .retry import retry_async
from .security import InputValidator, RateLimiter


class FileSystemManager:
    """
    Manages file I/O operations with safety features:
    - File locking to prevent concurrent modifications
    - Content hashing for conflict detection
    - Markdown section parsing
    - Path validation and sandboxing
    """

    def __init__(self, project_root: Path):
        """
        Initialize file system manager.

        Design Decision: File locking strategy
        Context: Need to prevent concurrent writes causing data corruption
        Decision: Use simple file-based locking with timeout
        Alternatives Considered: OS-level locks (fcntl), database locks
        Rationale: File locks are cross-platform and don't require external dependencies

        Args:
            project_root: Root directory of the project (for path validation)
        """
        self.project_root: Path = Path(project_root).resolve()
        self.memory_bank_dir: Path = self.project_root / ".cortex" / "memory-bank"
        self.lock_timeout: int = 5  # seconds
        self.rate_limiter: RateLimiter = RateLimiter(
            max_ops=RATE_LIMIT_OPS_PER_SECOND, window_seconds=1.0
        )

    def validate_path(self, file_path: Path) -> bool:
        """
        Validate that file path is within project root (prevent directory traversal).

        Args:
            file_path: Path to validate

        Returns:
            True if path is valid and safe
        """
        try:
            resolved = Path(file_path).resolve()
            return resolved.is_relative_to(self.project_root)
        except (ValueError, OSError):
            return False

    def validate_file_name(self, file_name: str) -> str:
        """
        Validate file name for security (path traversal, invalid characters, etc.).

        Args:
            file_name: File name to validate

        Returns:
            Validated file name

        Raises:
            ValueError: If file name is invalid
        """
        return InputValidator.validate_file_name(file_name)

    def construct_safe_path(self, base_dir: Path, file_name: str) -> Path:
        """
        Construct a safe file path by validating the file name and base directory.

        Args:
            base_dir: Base directory for the file
            file_name: Name of the file

        Returns:
            Safe path within base directory

        Raises:
            ValueError: If file name or path is invalid
            PermissionError: If path would be outside project root
        """
        # Validate file name first
        validated_name = self.validate_file_name(file_name)

        # Construct path
        file_path = base_dir / validated_name

        # Validate path is within project root
        if not self.validate_path(file_path):
            raise PermissionError(
                f"Failed to construct safe path for '{file_name}': Path {file_path} is outside project root '{self.project_root}'. Try: Ensure file name doesn't contain '..' or absolute paths, or verify project root is correctly configured."
            )

        # Additional check using InputValidator
        _ = InputValidator.validate_path(file_path, self.project_root)

        return file_path

    async def read_file(self, file_path: Path) -> tuple[str, str]:
        """
        Read file content and compute hash with retry logic.

        Args:
            file_path: Path to file to read

        Returns:
            Tuple of (content, sha256_hash)

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be read
        """
        # Rate limiting
        await self.rate_limiter.acquire()

        if not self.validate_path(file_path):
            raise PermissionError(
                f"Failed to read '{file_path.name}': Path {file_path} is outside project root '{self.project_root}'. Try: Check file path is correct and within project directory, or verify project root configuration."
            )

        async def read_operation() -> tuple[str, str]:
            async with open_async_text_file(file_path, "r", "utf-8") as f:
                content = await f.read()
            content_hash = self.compute_hash(content)
            return content, content_hash

        return await retry_async(
            read_operation,
            max_retries=3,
            base_delay=0.5,
            exceptions=(OSError, IOError, PermissionError),
        )

    async def write_file(
        self,
        file_path: Path,
        content: str,
        expected_hash: str | None = None,
    ) -> str:
        """
        Write file content with locking, conflict detection, and retry logic.

        Args:
            file_path: Path to file to write
            content: Content to write
            expected_hash: Expected current hash (for conflict detection)

        Returns:
            New content hash

        Raises:
            FileConflictError: If file was modified externally
            FileLockTimeoutError: If unable to acquire lock
            PermissionError: If path is invalid
        """
        await self.rate_limiter.acquire()
        self._validate_write_path(file_path)
        self._validate_write_content(file_path, content)
        lock_path = file_path.with_suffix(file_path.suffix + ".lock")
        write_operation = self._create_write_operation(
            file_path, content, expected_hash, lock_path
        )
        return await retry_async(
            write_operation,
            max_retries=3,
            base_delay=0.5,
            exceptions=(OSError, IOError, PermissionError, BlockingIOError),
        )

    def _create_write_operation(
        self,
        file_path: Path,
        content: str,
        expected_hash: str | None,
        lock_path: Path,
    ) -> Callable[[], Awaitable[str]]:
        """Create write operation function."""

        async def write_operation() -> str:
            try:
                await self.acquire_lock(lock_path)
                await self._check_file_conflict(file_path, expected_hash)
                await self._write_file_content(file_path, content)
                return self.compute_hash(content)
            finally:
                await self.release_lock(lock_path)

        return write_operation

    async def _check_file_conflict(
        self, file_path: Path, expected_hash: str | None
    ) -> None:
        """Check for file conflicts."""
        if expected_hash and file_path.exists():
            _, current_hash = await self.read_file(file_path)
            if current_hash != expected_hash:
                raise FileConflictError(
                    file_name=file_path.name,
                    expected_hash=expected_hash,
                    actual_hash=current_hash,
                )

    async def _write_file_content(self, file_path: Path, content: str) -> None:
        """Write file content."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with open_async_text_file(file_path, "w", "utf-8") as f:
            _ = await f.write(content)

    def _validate_write_path(self, file_path: Path) -> None:
        """Validate file path for writing."""
        if not self.validate_path(file_path):
            raise PermissionError(
                f"Failed to write '{file_path.name}': Path {file_path} is outside project root '{self.project_root}'. Try: Check file path is correct and within project directory, or verify project root configuration."
            )

    def _validate_write_content(self, file_path: Path, content: str) -> None:
        """Validate file content for writing."""
        if self.has_git_conflicts(content):
            raise GitConflictError(
                f"Failed to write '{file_path.name}': Git conflict markers detected in content. Cause: File contains unresolved git merge conflicts (<<<<<<, =======, >>>>>>>). Try: Resolve git conflicts manually and remove conflict markers before saving."
            )

    async def acquire_lock(self, lock_path: Path):
        """
        Acquire file lock with timeout.

        Args:
            lock_path: Path to lock file

        Raises:
            FileLockTimeoutError: If unable to acquire lock within timeout
        """
        start_time = asyncio.get_event_loop().time()

        # Cache the lock path existence check to avoid repeated I/O
        # Check once before entering loop
        lock_exists = lock_path.exists()

        while lock_exists:
            if (asyncio.get_event_loop().time() - start_time) > float(
                self.lock_timeout
            ):
                raise FileLockTimeoutError(
                    file_name=lock_path.stem,
                    timeout_seconds=self.lock_timeout,
                )
            await asyncio.sleep(LOCK_POLL_INTERVAL_SECONDS)
            # Only check existence after sleep
            lock_exists = lock_path.exists()

        # Ensure parent directory exists before creating lock file
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Create lock file
        lock_path.touch()

    async def release_lock(self, lock_path: Path):
        """
        Release file lock.

        Args:
            lock_path: Path to lock file
        """
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError:
            # Lock file already removed or inaccessible - not critical
            pass

    def compute_hash(self, content: str) -> str:
        """
        Compute SHA-256 hash of content.

        Args:
            content: Content to hash

        Returns:
            SHA-256 hash as hex string with 'sha256:' prefix
        """
        return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()

    def parse_sections(self, content: str) -> list[dict[str, str | int]]:
        """
        Parse markdown content into sections based on headings.

        Args:
            content: Markdown file content

        Returns:
            List of section dictionaries:
            [
                {
                    "heading": "## Section Name",
                    "level": 2,
                    "line_start": 5,
                    "line_end": 15,
                    "content_hash": "sha256:..."
                }
            ]
        """
        lines = content.split("\n")
        sections: list[dict[str, str | int]] = []
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
        current_section = None

        for i, line in enumerate(lines, start=1):
            match = heading_pattern.match(line)

            if match:
                if current_section:
                    current_section = self._close_section(
                        current_section, i, sections, lines
                    )

                level = len(match.group(1))
                current_section = {
                    "heading": line.strip(),
                    "level": level,
                    "line_start": i,
                    "line_end": len(lines),
                }

        if current_section:
            current_section = self._close_section(
                current_section, len(lines) + 1, sections, lines
            )

        return sections

    def _close_section(
        self,
        current_section: dict[str, str | int],
        end_line: int,
        sections: list[dict[str, str | int]],
        lines: list[str],
    ) -> None:
        """Close a section and add it to sections list."""
        current_section["line_end"] = end_line - 1
        line_start = int(current_section["line_start"])
        line_end = int(current_section["line_end"])
        section_lines = lines[line_start - 1 : line_end]
        section_content = "\n".join(section_lines)
        current_section["content_hash"] = self.compute_hash(section_content)
        sections.append(current_section)

    def has_git_conflicts(self, content: str) -> bool:
        """
        Check if content contains Git conflict markers.

        Args:
            content: File content to check

        Returns:
            True if conflict markers found
        """
        conflict_markers = ["<<<<<<<", "=======", ">>>>>>>"]
        return any(marker in content for marker in conflict_markers)

    async def ensure_directory(self, dir_path: Path):
        """
        Ensure directory exists, create if it doesn't.

        Args:
            dir_path: Path to directory
        """
        if not self.validate_path(dir_path):
            raise PermissionError(
                f"Failed to create directory '{dir_path.name}': Path {dir_path} is outside project root '{self.project_root}'. Try: Ensure directory path is within project, or verify project root configuration."
            )

        dir_path.mkdir(parents=True, exist_ok=True)

    async def file_exists(self, file_path: Path) -> bool:
        """
        Check if file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists
        """
        if not self.validate_path(file_path):
            return False

        return file_path.exists() and file_path.is_file()

    async def get_file_size(self, file_path: Path) -> int:
        """
        Get file size in bytes.

        Args:
            file_path: Path to file

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not await self.file_exists(file_path):
            raise FileNotFoundError(
                f"Failed to get file size for '{file_path.name}': File not found at {file_path}. Try: Check file path is correct, verify file exists, or run initialize_memory_bank() to create missing files."
            )

        return file_path.stat().st_size

    async def get_modification_time(self, file_path: Path) -> float:
        """
        Get file modification time.

        Args:
            file_path: Path to file

        Returns:
            Modification time as Unix timestamp

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not await self.file_exists(file_path):
            raise FileNotFoundError(
                f"Failed to get modification time for '{file_path.name}': File not found at {file_path}. Try: Check file path is correct, verify file exists, or run initialize_memory_bank() to create missing files."
            )

        return file_path.stat().st_mtime

    async def cleanup_locks(self):
        """
        Clean up any stale lock files in memory-bank directory.
        Should be called on server startup.
        """
        if not self.memory_bank_dir.exists():
            return

        for lock_file in self.memory_bank_dir.glob("*.lock"):
            try:
                lock_file.unlink()
            except OSError:
                # Lock file inaccessible - skip
                pass
