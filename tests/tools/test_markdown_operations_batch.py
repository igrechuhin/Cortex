"""Tests for markdown operations sequential processing."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.markdown_operations import (
    FileResult,
    _process_markdown_files_sequential,  # pyright: ignore[reportPrivateUsage]
)


class TestSequentialProcessing:
    """Test sequential processing functionality."""

    @pytest.mark.asyncio
    async def test_process_markdown_files_all_files(self):
        """Test that all files are processed sequentially."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            files = [project_root / f"file{i}.md" for i in range(10)]
            for f in files:
                _ = f.write_text("# Test\n")

            markdownlint_cmd = ["markdownlint-cli2"]
            call_count = 0

            async def mock_run_markdownlint_batch(
                file_paths: list[Path],
                root: Path,
                cmd: list[str],
                config_path: Path | None,
                dry_run: bool,
            ) -> list[FileResult]:
                nonlocal call_count
                call_count += 1
                return [
                    FileResult(
                        file=str(file_path.relative_to(root)),
                        fixed=False,
                        errors=[],
                        error_message=None,
                    )
                    for file_path in file_paths
                ]

            # Act
            with patch(
                "cortex.tools.markdown_lint_run._run_markdownlint_batch",
                side_effect=mock_run_markdownlint_batch,
            ):
                results: list[FileResult] = await _process_markdown_files_sequential(
                    files,
                    project_root,
                    markdownlint_cmd,
                    None,
                    False,
                )

            # Assert
            assert len(results) == 10
            assert call_count == 1  # All files processed in a single batch

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

            async def mock_run_markdownlint_batch(
                file_paths: list[Path],
                root: Path,
                cmd: list[str],
                config_path: Path | None,
                dry_run: bool,
            ) -> list[FileResult]:
                results: list[FileResult] = []
                for file_path in file_paths:
                    rel = str(file_path.relative_to(root))
                    if "file2" in rel:
                        results.append(
                            FileResult(
                                file=rel,
                                fixed=False,
                                errors=[],
                                error_message="Test error",
                            )
                        )
                    else:
                        results.append(
                            FileResult(
                                file=rel,
                                fixed=False,
                                errors=[],
                                error_message=None,
                            )
                        )
                return results

            # Act
            with patch(
                "cortex.tools.markdown_lint_run._run_markdownlint_batch",
                side_effect=mock_run_markdownlint_batch,
            ):
                results: list[FileResult] = await _process_markdown_files_sequential(
                    files,
                    project_root,
                    markdownlint_cmd,
                    None,
                    False,
                )

            # Assert
            assert len(results) == 5
            # Find the error result
            error_results: list[FileResult] = [r for r in results if r.error_message]
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

            async def mock_run_markdownlint_batch(
                file_paths: list[Path],
                root: Path,
                cmd: list[str],
                config_path: Path | None,
                dry_run: bool,
            ) -> list[FileResult]:
                return [
                    FileResult(
                        file=str(file_path.relative_to(root)),
                        fixed=False,
                        errors=[],
                        error_message=None,
                    )
                    for file_path in file_paths
                ]

            # Act
            with patch(
                "cortex.tools.markdown_lint_run._run_markdownlint_batch",
                side_effect=mock_run_markdownlint_batch,
            ):
                results: list[FileResult] = await _process_markdown_files_sequential(
                    files,
                    project_root,
                    markdownlint_cmd,
                    None,
                    False,
                )

            # Assert
            # Should only process existing files
            assert len(results) == 2
            file_names: set[str] = {r.file for r in results}
            assert "exists.md" in file_names
            assert "also_exists.md" in file_names
            assert "nonexistent.md" not in file_names

    @pytest.mark.asyncio
    async def test_process_markdown_files_reports_progress_every_file_and_heartbeat_cancelled(
        self,
    ):
        """With progress_ctx set, progress is reported after every file; heartbeat task is cancelled on exit."""
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            files = [
                project_root / "a.md",
                project_root / "b.md",
                project_root / "c.md",
            ]
            for f in files:
                _ = f.write_text("# x\n")
            markdownlint_cmd = ["markdownlint-cli2"]
            mock_ctx = AsyncMock()
            progress_calls: list[tuple[float, float]] = []

            async def capture_progress(progress: float, total: float | None) -> None:
                if total is not None:
                    progress_calls.append((progress, total))

            mock_ctx.report_progress = capture_progress

            async def mock_run_markdownlint_batch(
                file_paths: list[Path],
                root: Path,
                cmd: list[str],
                config_path: Path | None,
                dry_run: bool,
            ) -> list[FileResult]:
                return [
                    FileResult(
                        file=str(file_path.relative_to(root)),
                        fixed=False,
                        errors=[],
                        error_message=None,
                    )
                    for file_path in file_paths
                ]

            with patch(
                "cortex.tools.markdown_lint_run._run_markdownlint_batch",
                side_effect=mock_run_markdownlint_batch,
            ):
                results: list[FileResult] = await _process_markdown_files_sequential(
                    files,
                    project_root,
                    markdownlint_cmd,
                    None,
                    False,
                    progress_ctx=mock_ctx,
                    progress_total=3,
                )

            assert len(results) == 3
            # Progress after each file: (1,3), (2,3), (3,3); may also have (0,3) from start
            assert (1.0, 3.0) in progress_calls
            assert (2.0, 3.0) in progress_calls
            assert (3.0, 3.0) in progress_calls
            assert len(progress_calls) >= 3


class TestRoadmapCorruption:
    """Test roadmap corruption detection and fixing."""

    def test_detect_roadmap_corruption_missing_space(self):
        """Test detection of missing space after completion date."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "Target completion:2026-01-20Fix"
        matches = detect_roadmap_corruption(content)
        assert len(matches) > 0
        # Should detect missing space (could be multiple patterns)
        patterns = {m.pattern for m in matches}
        assert any("space" in p or "completion" in p for p in patterns)

    def test_detect_roadmap_corruption_corrupted_phase(self):
        """Test detection of corrupted phase numbers."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "Phase 5% rate"
        matches = detect_roadmap_corruption(content)
        assert len(matches) > 0
        assert matches[0].pattern == "corrupted_phase_number"
        assert "Phase 5: Validate" in matches[0].fixed

    def test_detect_roadmap_corruption_ented(self):
        """Test detection of 'ented' corruption."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "Feature ented successfully"
        matches = detect_roadmap_corruption(content)
        assert len(matches) > 0
        assert matches[0].pattern == "corrupted_implemented"
        assert "Implemented" in matches[0].fixed

    def test_detect_roadmap_corruption_percent_to(self):
        """Test detection of percent+to corruption (e.g. 89.89to -> 89.89% to)."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "Coverage 89.89to 90%"
        matches = detect_roadmap_corruption(content)
        assert len(matches) >= 1
        assert any(m.pattern == "percent_to_missing_space" for m in matches)
        fixed_match = next(
            m for m in matches if m.pattern == "percent_to_missing_space"
        )
        assert fixed_match.fixed == "89.89% to"

    def test_detect_roadmap_corruption_number_actual(self):
        """Test detection of number+ctual corruption (e.g. 0ctual -> 0 actual)."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "0ctual completion"
        matches = detect_roadmap_corruption(content)
        assert len(matches) >= 1
        assert any(m.pattern == "number_actual_missing_space" for m in matches)
        fixed_match = next(
            m for m in matches if m.pattern == "number_actual_missing_space"
        )
        assert fixed_match.fixed == "0 actual"

    def test_detect_roadmap_corruption_ceeds_percent(self):
        """Test detection of ceeds+digit corruption (e.g. ceeds90 -> (exceeds 90%)."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "Threshold ceeds90"
        matches = detect_roadmap_corruption(content)
        assert len(matches) >= 1
        assert any(m.pattern == "exceeds_percent_corrupted" for m in matches)
        fixed_match = next(
            m for m in matches if m.pattern == "exceeds_percent_corrupted"
        )
        assert fixed_match.fixed == "(exceeds 90%"

    def test_detect_roadmap_corruption_files_unchanged(self):
        """Test detection of number+es unchanged (e.g. 285es -> 285 files)."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "285es unchanged"
        matches = detect_roadmap_corruption(content)
        assert len(matches) >= 1
        assert any(m.pattern == "files_unchanged_corrupted" for m in matches)
        fixed_match = next(
            m for m in matches if m.pattern == "files_unchanged_corrupted"
        )
        assert fixed_match.fixed == "285 files unchanged"

    def test_detect_roadmap_corruption_malformed_date_fixed(self):
        """Test detection of 2026MM-DDixed -> 2026-MM-DD) - Fixed."""
        from cortex.tools.roadmap_corruption import detect_roadmap_corruption

        content = "Target 202601-15ixed"
        matches = detect_roadmap_corruption(content)
        assert len(matches) >= 1
        assert any(m.pattern == "malformed_date_fixed" for m in matches)
        fixed_match = next(m for m in matches if m.pattern == "malformed_date_fixed")
        assert fixed_match.fixed == "2026-01-15) - Fixed"
