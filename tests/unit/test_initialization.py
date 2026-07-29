#!/usr/bin/env python3
"""
Unit tests for initialization module.

Tests project root detection and manager initialization.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
    has_memory_bank,
)
from cortex.managers.initialization import get_project_root

# ============================================================================
# Test get_project_root
# ============================================================================


class TestGetProjectRoot:
    """Test get_project_root function."""

    def test_get_project_root_with_explicit_path(self, tmp_path: Path) -> None:
        """Test get_project_root returns resolved path when provided and valid."""
        # Arrange: path must contain .cortex/memory-bank to be accepted
        project_root = tmp_path / "project"
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).mkdir(
            parents=True
        )

        # Act
        result = get_project_root(str(project_root))

        # Assert
        assert result == project_root.resolve()
        assert result.is_absolute()

    def test_get_project_root_detects_from_cortex_dir(self, tmp_path: Path) -> None:
        """Test get_project_root detects project root from .cortex/ directory."""
        # Arrange
        project_root = tmp_path / "project"
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).mkdir(
            parents=True
        )
        subdir = project_root / "subdir" / "nested"
        subdir.mkdir(parents=True)

        # Act - call from nested subdirectory
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=subdir),
            patch("sys.argv", [str(subdir / "script.py")]),
        ):
            result = get_project_root(None)

        # Assert
        assert result == project_root.resolve()
        assert result.is_absolute()

    def test_get_project_root_falls_back_to_cwd_when_no_cortex(
        self, tmp_path: Path
    ) -> None:
        """Test get_project_root falls back to cwd when .cortex/ not found."""
        # Arrange
        no_cortex_dir = tmp_path / "no-cortex"
        no_cortex_dir.mkdir()

        # Act
        with (
            patch(
                "cortex.managers.initialization.Path.cwd", return_value=no_cortex_dir
            ),
            patch("sys.argv", [str(no_cortex_dir / "script.py")]),
        ):
            result = get_project_root(None)

        # Assert
        assert result == no_cortex_dir.resolve()
        assert result.is_absolute()

    def test_get_project_root_detects_from_parent(self, tmp_path: Path) -> None:
        """Test get_project_root detects project root in parent directory."""
        # Arrange
        project_root = tmp_path / "project"
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).mkdir(
            parents=True
        )
        subdir = project_root / "deep" / "nested"
        subdir.mkdir(parents=True)

        # Act - call from deep nested subdirectory
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=subdir),
            patch("sys.argv", [str(subdir / "script.py")]),
        ):
            result = get_project_root(None)

        # Assert
        assert result == project_root.resolve()
        assert result.is_absolute()

    def test_get_project_root_resolves_relative_path(self, tmp_path: Path) -> None:
        """Test get_project_root resolves relative paths when path is valid."""
        # Arrange: path must contain .cortex/memory-bank
        project_root = tmp_path / "project"
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).mkdir(
            parents=True
        )
        original_cwd = Path.cwd()

        try:
            os.chdir(tmp_path)
            relative_path = "project"

            # Act
            result = get_project_root(relative_path)

            # Assert
            assert result == project_root.resolve()
            assert result.is_absolute()
        finally:
            os.chdir(original_cwd)

    def test_get_project_root_falls_back_when_explicit_path_is_subdir_of_cortex_root(
        self, tmp_path: Path
    ) -> None:
        """When explicit path is a subdir of a Cortex root (e.g. segment 'optimization'),
        fall back to auto-detect so we do not use that subdir as project root and
        create spurious dirs (e.g. repo/optimization/.cortex/) at repo root."""
        # Arrange: repo has .cortex/memory-bank; subdir does not
        project_root = tmp_path / "repo"
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).mkdir(
            parents=True
        )
        subdir = project_root / "subdir"
        subdir.mkdir(parents=True)

        # Act: pass path that resolves to subdir of Cortex root
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=project_root),
            patch("sys.argv", [str(project_root / "main.py")]),
        ):
            result = get_project_root(str(subdir))

        # Assert: fall back to auto-detect and return Cortex root, not subdir
        assert result == project_root.resolve()
        assert result.is_absolute()
        assert has_memory_bank(result)

    def test_get_project_root_returns_explicit_path_when_not_under_cortex_root(
        self, tmp_path: Path
    ) -> None:
        """When explicit path has no .cortex and its parent is not a Cortex root, return it."""
        # Arrange: path outside any Cortex repo
        other = tmp_path / "other"
        other.mkdir(parents=True)

        # Act
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=tmp_path),
            patch("sys.argv", [str(tmp_path / "main.py")]),
        ):
            result = get_project_root(str(other))

        # Assert: return the path the caller asked for
        assert result == other.resolve()
        assert result.is_absolute()

    def test_get_project_root_falls_back_when_relative_segment_resolves_under_cortex(
        self, tmp_path: Path
    ) -> None:
        """When client passes a relative segment (e.g. 'optimization'), resolve yields
        repo/optimization; we fall back to auto-detect to avoid creating repo/optimization/.cortex/.
        """
        # Arrange: Cortex root at repo; cwd is repo so relative 'optimization' -> repo/optimization
        project_root = tmp_path / "repo"
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).mkdir(
            parents=True
        )
        (project_root / "optimization").mkdir(parents=True)

        # Act: pass relative segment name (as a client might when context is a subdir)
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=project_root),
            patch("sys.argv", [str(project_root / "main.py")]),
        ):
            result = get_project_root("optimization")

        # Assert: fall back to Cortex root, not repo/optimization
        assert result == project_root.resolve()
        assert has_memory_bank(result)

    def test_get_project_root_prefers_repo_over_subdir_with_cortex(
        self, tmp_path: Path
    ) -> None:
        """When explicit path is a subdir that has .cortex/memory-bank, prefer repo root."""
        # Arrange: repo and subdir both have .cortex/memory-bank
        repo_root = tmp_path / "repo"
        get_cortex_path(repo_root, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        sub = repo_root / "sub"
        get_cortex_path(sub, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        # Act: pass absolute subdir path; cwd is repo so candidates stay under tmp_path
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=repo_root),
            patch("sys.argv", [str(repo_root / "main.py")]),
        ):
            result = get_project_root(str(sub))

        # Assert: should return repo root, not sub (avoids .cortex/.cache under structure/)
        assert result == repo_root.resolve()
        assert result.is_absolute()
        assert has_memory_bank(result)

    def test_get_project_root_prefers_repo_when_cwd_is_subdir_with_cortex(
        self, tmp_path: Path
    ) -> None:
        """When cwd is a subdir that has .cortex, prefer repo from script."""
        # Arrange: repo and sub both have .cortex/memory-bank; cwd is sub
        repo_root = tmp_path / "repo"
        get_cortex_path(repo_root, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        sub = repo_root / "sub"
        get_cortex_path(sub, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        # Act: pass absolute sub path; cwd=sub, script in repo → prefer repo root
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=sub),
            patch("sys.argv", [str(repo_root / "main.py")]),
        ):
            result = get_project_root(str(sub))

        # Assert: should return repo root (topmost from script), not sub
        assert result == repo_root.resolve()
        assert result.is_absolute()
        assert has_memory_bank(result)

    def test_get_project_root_rejects_optimization_package_subdir_as_root(
        self, tmp_path: Path
    ) -> None:
        """When path is a subdir with .cortex under repo, return repo root."""
        # Arrange: repo has .cortex and src/; sub has .cortex (wrongly)
        repo_root = tmp_path / "repo"
        get_cortex_path(repo_root, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        (repo_root / "src").mkdir()
        sub = repo_root / "sub"
        get_cortex_path(sub, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        # Act: pass sub path (no script); walk up to repo root
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=sub),
            patch("sys.argv", []),
        ):
            result = get_project_root(str(sub))

        # Assert: return repo root, not sub
        assert result == repo_root.resolve()
        assert (result / "src").is_dir()
        assert has_memory_bank(result)

    def test_get_project_root_rejects_learning_nested_under_refactoring(
        self, tmp_path: Path
    ) -> None:
        """When path is nested under repo with .cortex, return repo root."""
        # Arrange: repo has .cortex and src/; src/nested has .cortex (wrongly)
        repo_root = tmp_path / "repo"
        get_cortex_path(repo_root, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        (repo_root / "src").mkdir()
        nested = repo_root / "src" / "nested"
        get_cortex_path(nested, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        # Act: pass nested path; walk up to repo root
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=nested),
            patch("sys.argv", []),
        ):
            result = get_project_root(str(nested))

        # Assert: return repo root, not nested
        assert result == repo_root.resolve()
        assert (result / "src").is_dir()
        assert has_memory_bank(result)

    def test_get_project_root_rejects_invalid_sibling_with_cortex(
        self, tmp_path: Path
    ) -> None:
        """When path is sibling of src/ with .cortex, return repo root."""
        # Arrange: repo has .cortex and src/; invalid (sibling of src/) has .cortex
        repo_root = tmp_path / "repo"
        get_cortex_path(repo_root, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        (repo_root / "src").mkdir()
        invalid_dir = repo_root / "invalid"
        get_cortex_path(invalid_dir, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        # Act: pass invalid path; walk up to repo root
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=invalid_dir),
            patch("sys.argv", []),
        ):
            result = get_project_root(str(invalid_dir))

        # Assert: return repo root, not invalid
        assert result == repo_root.resolve()
        assert (result / "src").is_dir()
        assert has_memory_bank(result)

    def test_get_project_root_rejects_consolidation_subdir_with_cortex(
        self, tmp_path: Path
    ) -> None:
        """When path is nested under repo with .cortex, return repo root."""
        # Arrange: repo has .cortex and src/; src/nested has .cortex (wrongly)
        repo_root = tmp_path / "repo"
        get_cortex_path(repo_root, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        (repo_root / "src").mkdir()
        nested = repo_root / "src" / "nested"
        get_cortex_path(nested, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        # Act: pass nested path; walk up to repo root
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=nested),
            patch("sys.argv", []),
        ):
            result = get_project_root(str(nested))

        # Assert: return repo root, not nested
        assert result == repo_root.resolve()
        assert (result / "src").is_dir()
        assert has_memory_bank(result)

    def test_get_project_root_handles_root_filesystem(self) -> None:
        """Test get_project_root handles root filesystem correctly."""
        # Arrange
        root_path = Path("/")

        # Act
        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=root_path),
            patch("sys.argv", ["/script.py"]),
        ):
            result = get_project_root(None)

        # Assert
        assert result == root_path.resolve()
        assert result.is_absolute()

    def test_get_project_root_skips_partial_home_dir_cortex_init(
        self, tmp_path: Path
    ) -> None:
        """Partial ~/.cortex/memory-bank (from a prior global-config run) must not
        be selected as the project root; the real project root should win instead."""
        # Arrange: simulate home dir with partial Cortex init (no 7 core files)
        fake_home = tmp_path / "home"
        get_cortex_path(fake_home, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        # Real project at a different path with fully initialized memory bank
        project_root = tmp_path / "Repo" / "TradeWing"
        mb_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        mb_dir.mkdir(parents=True)
        core_files = [
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ]
        for fname in core_files:
            _ = (mb_dir / fname).write_text("# test")

        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=fake_home),
            patch("cortex.managers.initialization.Path.home", return_value=fake_home),
            patch("sys.argv", [str(fake_home / "script.py")]),
        ):
            result = get_project_root(str(project_root))

        assert result == project_root.resolve()

    def test_get_project_root_cwd_at_home_with_partial_cortex_skips_home_dir(
        self, tmp_path: Path
    ) -> None:
        """_find_root_from_cwd skips home dir if it has only a partial Cortex init."""
        fake_home = tmp_path / "home"
        get_cortex_path(fake_home, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=fake_home),
            patch("cortex.managers.initialization.Path.home", return_value=fake_home),
            patch("sys.argv", [str(fake_home / "script.py")]),
        ):
            result = get_project_root(None)

        # Home dir has no fully-initialized memory bank → _find_root_from_cwd
        # skips it → candidates=[] → falls back to Path.cwd() but NOT a cortex root
        assert result == fake_home.resolve()
        # Crucially: the result must NOT be treated as having a memory bank by
        # is_memory_bank_fully_initialized (it doesn't have the 7 core files).
        from cortex.core.path_resolver import is_memory_bank_fully_initialized

        assert not is_memory_bank_fully_initialized(result)

    @pytest.mark.parametrize(
        "marker",
        ["Package.swift", "TradeWing.xcodeproj", "TradeWing.xcworkspace"],
    )
    def test_get_project_root_stops_at_swift_project_not_home_cortex(
        self, tmp_path: Path, marker: str
    ) -> None:
        """A Swift repo nested under a home dir with .cortex must win over the home dir.

        Regression: _has_language_markers only knew pyproject.toml/package.json/
        Cargo.toml/go.mod/go.sum, so a Swift project failed the "looks like a real
        project root" check. _reject_package_subdir_as_root then walked up past it
        and returned the home dir, making every validator resolve project-relative
        paths against ~/.cortex instead of the repo.
        """
        fake_home = tmp_path / "home"
        get_cortex_path(fake_home, CortexResourceType.MEMORY_BANK).mkdir(parents=True)

        project_root = fake_home / "Repo" / "TradeWing"
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).mkdir(
            parents=True
        )
        # .xcodeproj/.xcworkspace are directories; Package.swift is a file.
        if marker.endswith(".swift"):
            _ = (project_root / marker).write_text("// swift-tools-version:6.1")
        else:
            (project_root / marker).mkdir()

        with (
            patch("cortex.managers.initialization.Path.cwd", return_value=project_root),
            patch("cortex.managers.initialization.Path.home", return_value=fake_home),
            patch("sys.argv", [str(project_root / "script.py")]),
        ):
            result = get_project_root(None)

        assert result == project_root.resolve()
