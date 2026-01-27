"""Tests for markdown operations batch processing and concurrency."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from cortex.tools.markdown_operations import (
    FileResult,
    _process_markdown_files,  # pyright: ignore[reportPrivateUsage]
)


class TestBatchProcessing:
    """Test batch processing functionality."""

    @pytest.mark.asyncio
    async def test_process_markdown_files_batches(self):
        """Test that files are processed in batches."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            files = [project_root / f"file{i}.md" for i in range(100)]
            for f in files:
                _ = f.write_text("# Test\n")

            markdownlint_cmd = ["markdownlint-cli2"]
            call_count = 0

            async def mock_run_markdownlint_fix(
                file_path: Path, root: Path, cmd: list[str], dry_run: bool
            ) -> FileResult:
                nonlocal call_count
                call_count += 1
                return FileResult(
                    file=str(file_path.relative_to(root)),
                    fixed=False,
                    errors=[],
                    error_message=None,
                )

            # Act
            with patch(
                "cortex.tools.markdown_operations._run_markdownlint_fix",
                side_effect=mock_run_markdownlint_fix,
            ):
                results = await _process_markdown_files(
                    files,
                    project_root,
                    markdownlint_cmd,
                    False,
                    max_concurrent=5,
                    batch_size=20,
                )

            # Assert
            assert len(results) == 100
            assert call_count == 100  # All files processed

    @pytest.mark.asyncio
    async def test_process_markdown_files_concurrency_limit(self):
        """Test that concurrency is limited by semaphore."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            files = [project_root / f"file{i}.md" for i in range(10)]
            for f in files:
                _ = f.write_text("# Test\n")

            markdownlint_cmd = ["markdownlint-cli2"]
            concurrent_count = 0
            max_concurrent_seen = 0

            async def mock_run_markdownlint_fix(
                file_path: Path, root: Path, cmd: list[str], dry_run: bool
            ) -> FileResult:
                nonlocal concurrent_count, max_concurrent_seen
                concurrent_count += 1
                max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
                await asyncio.sleep(0.01)  # Small delay to allow concurrency
                concurrent_count -= 1
                return FileResult(
                    file=str(file_path.relative_to(root)),
                    fixed=False,
                    errors=[],
                    error_message=None,
                )

            # Act
            with patch(
                "cortex.tools.markdown_operations._run_markdownlint_fix",
                side_effect=mock_run_markdownlint_fix,
            ):
                results = await _process_markdown_files(
                    files,
                    project_root,
                    markdownlint_cmd,
                    False,
                    max_concurrent=3,
                    batch_size=10,
                )

            # Assert
            assert len(results) == 10
            assert max_concurrent_seen <= 3  # Should not exceed concurrency limit

    @pytest.mark.asyncio
    async def test_process_markdown_files_handles_exceptions(self):
        """Test that exceptions are properly handled and converted to error results."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            files = [project_root / f"file{i}.md" for i in range(5)]
            for f in files:
                _ = f.write_text("# Test\n")

            markdownlint_cmd = ["markdownlint-cli2"]

            async def mock_run_markdownlint_fix(
                file_path: Path, root: Path, cmd: list[str], dry_run: bool
            ) -> FileResult:
                if "file2" in str(file_path):
                    raise ValueError("Test error")
                return FileResult(
                    file=str(file_path.relative_to(root)),
                    fixed=False,
                    errors=[],
                    error_message=None,
                )

            # Act
            with patch(
                "cortex.tools.markdown_operations._run_markdownlint_fix",
                side_effect=mock_run_markdownlint_fix,
            ):
                results = await _process_markdown_files(
                    files,
                    project_root,
                    markdownlint_cmd,
                    False,
                    max_concurrent=5,
                    batch_size=10,
                )

            # Assert
            assert len(results) == 5
            # Find the error result
            error_results = [r for r in results if r.error_message]
            assert len(error_results) == 1
            error_msg = error_results[0].error_message
            assert error_msg is not None
            assert "Test error" in error_msg

    @pytest.mark.asyncio
    async def test_process_markdown_files_skips_nonexistent_files(self):
        """Test that nonexistent files are skipped."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            files = [
                project_root / "exists.md",
                project_root / "nonexistent.md",
                project_root / "also_exists.md",
            ]
            _ = (project_root / "exists.md").write_text("# Test\n")
            _ = (project_root / "also_exists.md").write_text("# Test\n")

            markdownlint_cmd = ["markdownlint-cli2"]

            # Act
            results = await _process_markdown_files(
                files,
                project_root,
                markdownlint_cmd,
                False,
                max_concurrent=5,
                batch_size=10,
            )

            # Assert
            # Should only process existing files
            assert len(results) == 2
            file_names = {r.file for r in results}
            assert "exists.md" in file_names
            assert "also_exists.md" in file_names
            assert "nonexistent.md" not in file_names


class TestRoadmapCorruption:
    """Test roadmap corruption detection and fixing."""

    def test_detect_roadmap_corruption_missing_space(self):
        """Test detection of missing space after completion date."""
        from cortex.tools.markdown_operations import (
            _detect_roadmap_corruption,  # pyright: ignore[reportPrivateUsage]
        )

        content = "Target completion:2026-01-20Fix"
        matches = _detect_roadmap_corruption(content)
        assert len(matches) > 0
        # Should detect missing space (could be multiple patterns)
        patterns = {m.pattern for m in matches}
        assert any("space" in p or "completion" in p for p in patterns)

    def test_detect_roadmap_corruption_corrupted_phase(self):
        """Test detection of corrupted phase numbers."""
        from cortex.tools.markdown_operations import (
            _detect_roadmap_corruption,  # pyright: ignore[reportPrivateUsage]
        )

        content = "Phase 5% rate"
        matches = _detect_roadmap_corruption(content)
        assert len(matches) > 0
        assert matches[0].pattern == "corrupted_phase_number"
        assert "Phase 5: Validate" in matches[0].fixed

    def test_detect_roadmap_corruption_ented(self):
        """Test detection of 'ented' corruption."""
        from cortex.tools.markdown_operations import (
            _detect_roadmap_corruption,  # pyright: ignore[reportPrivateUsage]
        )

        content = "Feature ented successfully"
        matches = _detect_roadmap_corruption(content)
        assert len(matches) > 0
        assert matches[0].pattern == "corrupted_implemented"
        assert "Implemented" in matches[0].fixed
