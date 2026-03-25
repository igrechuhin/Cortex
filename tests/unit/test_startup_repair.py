"""Unit tests for cortex.structure.lifecycle.startup_repair."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.structure.lifecycle.startup_repair import (
    AGENT_SYNC_MARKER,
    GITIGNORE_MARKER,
    RUMDL_TOML_MARKER,
    repair_project_setup,
)
from cortex.structure.structure_config import StructureConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_git_repo(root: Path) -> None:
    """Create a minimal .git directory so the project is treated as a git repo."""
    (root / ".git").mkdir()


def _make_full_structure(root: Path) -> None:
    """Create a fully initialised .cortex/ structure (dirs + config)."""
    config = StructureConfig(root)
    for key in (
        "root",
        "memory_bank",
        "rules",
        "plans",
        "config",
        "archived",
        "reviews",
    ):
        config.get_path(key).mkdir(parents=True, exist_ok=True)
    # Create plans sub-dirs expected by setup
    for sub in ("templates", "active", "completed", "archived"):
        (config.get_path("plans") / sub).mkdir(exist_ok=True)
    (config.get_path("rules") / "local").mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repair_skips_healthy_project(tmp_path: Path) -> None:
    # Arrange – all needs-checks report healthy; repair should be skipped.
    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_gitignore",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_rumdl_config",
            return_value=False,
        ),
    ):
        # Act
        report = await repair_project_setup(tmp_path)

    # Assert
    assert report.skipped is True
    assert report.structure_repaired is False
    assert report.symlinks_repaired is False
    assert report.gitignore_updated is False
    assert report.rumdl_config_updated is False
    assert report.errors == []


@pytest.mark.asyncio
async def test_repair_creates_missing_structure(tmp_path: Path) -> None:
    # Arrange – empty project root (no .cortex/ at all)
    # Patch cursor check so only structure triggers repair
    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_gitignore",
            return_value=False,
        ),
    ):
        # Act
        report = await repair_project_setup(tmp_path)

    # Assert
    assert report.structure_repaired is True
    assert (tmp_path / ".cortex" / "memory-bank").is_dir()
    assert (tmp_path / ".cortex" / "plans").is_dir()
    assert report.skipped is False


@pytest.mark.asyncio
async def test_repair_fixes_broken_symlink(tmp_path: Path) -> None:
    # Arrange – valid structure but broken symlink
    _make_full_structure(tmp_path)
    config = StructureConfig(tmp_path)
    # Point symlink_location to a test-safe dir (not .cursor which may be restricted)
    config.structure_config["cursor_integration"] = {
        "enabled": True,
        "symlink_location": "_cursor",
        "symlinks": {"memory_bank": True, "rules": False, "plans": False},
    }
    cursor_dir = tmp_path / "_cursor"
    cursor_dir.mkdir()
    # Create a broken symlink
    broken = cursor_dir / "memory-bank"
    broken.symlink_to("/nonexistent/path")

    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_gitignore",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=True,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair.StructureConfig",
            return_value=config,
        ),
    ):
        report = await repair_project_setup(tmp_path)

    # Assert
    assert report.symlinks_repaired is True
    assert report.skipped is False


@pytest.mark.asyncio
async def test_repair_appends_gitignore_entries(tmp_path: Path) -> None:
    # Arrange – git repo with .gitignore that lacks Cortex entries
    _make_git_repo(tmp_path)
    gitignore = tmp_path / ".gitignore"
    _ = gitignore.write_text("# existing\n*.pyc\n", encoding="utf-8")

    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
    ):
        # Act
        report = await repair_project_setup(tmp_path)

    # Assert
    assert report.gitignore_updated is True
    content = gitignore.read_text(encoding="utf-8")
    assert GITIGNORE_MARKER in content
    assert ".cortex/.cache/" in content
    assert ".cortex/history/" in content
    assert ".cortex-backup-*/" in content
    assert AGENT_SYNC_MARKER in content
    assert ".cursor/agents/" in content
    assert report.skipped is False


@pytest.mark.asyncio
async def test_repair_updates_gitignore_when_agent_marker_missing(
    tmp_path: Path,
) -> None:
    # Arrange – git repo, .gitignore has Cortex transient marker but not agent sync marker
    _make_git_repo(tmp_path)
    gitignore = tmp_path / ".gitignore"
    _ = gitignore.write_text(
        f"# existing\n{GITIGNORE_MARKER}\n",
        encoding="utf-8",
    )

    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
    ):
        report = await repair_project_setup(tmp_path)

    # Assert – updated because agent sync marker was absent
    assert report.gitignore_updated is True
    content = gitignore.read_text(encoding="utf-8")
    assert AGENT_SYNC_MARKER in content
    assert ".cursor/agents/" in content
    assert report.skipped is False


@pytest.mark.asyncio
async def test_repair_skips_gitignore_when_entries_present(tmp_path: Path) -> None:
    # Arrange – git repo, .gitignore already has both markers
    _make_git_repo(tmp_path)
    gitignore = tmp_path / ".gitignore"
    _ = gitignore.write_text(
        f"# existing\n{GITIGNORE_MARKER}\n{AGENT_SYNC_MARKER}\n",
        encoding="utf-8",
    )

    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_rumdl_config",
            return_value=False,
        ),
    ):
        report = await repair_project_setup(tmp_path)

    # Assert
    assert report.gitignore_updated is False
    assert report.skipped is True


@pytest.mark.asyncio
async def test_repair_skips_gitignore_when_no_git_dir(tmp_path: Path) -> None:
    # Arrange – no .git directory → not a git repo
    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_rumdl_config",
            return_value=False,
        ),
    ):
        report = await repair_project_setup(tmp_path)

    # Assert – gitignore not touched even though no .gitignore exists
    assert report.gitignore_updated is False
    assert report.skipped is True
    assert not (tmp_path / ".gitignore").exists()


@pytest.mark.asyncio
async def test_repair_is_fault_tolerant(tmp_path: Path) -> None:
    # Arrange – gitignore repair will raise
    _make_git_repo(tmp_path)

    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_gitignore",
            return_value=True,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._repair_gitignore",
            side_effect=OSError("disk full"),
        ),
    ):
        # Act – must not raise
        report = await repair_project_setup(tmp_path)

    # Assert – error recorded, no exception
    assert report.gitignore_updated is False
    assert report.skipped is False


@pytest.mark.asyncio
async def test_repair_creates_gitignore_when_missing(tmp_path: Path) -> None:
    # Arrange – git repo but no .gitignore file
    _make_git_repo(tmp_path)

    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
    ):
        report = await repair_project_setup(tmp_path)

    # Assert – .gitignore created with Cortex block
    assert report.gitignore_updated is True
    assert (tmp_path / ".gitignore").is_file()
    assert GITIGNORE_MARKER in (tmp_path / ".gitignore").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_repair_creates_rumdl_toml_when_missing(tmp_path: Path) -> None:
    # Arrange – no .rumdl.toml in project root
    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_gitignore",
            return_value=False,
        ),
    ):
        report = await repair_project_setup(tmp_path)

    # Assert – .rumdl.toml created with disable list
    assert report.rumdl_config_updated is True
    assert report.skipped is False
    rumdl_toml = tmp_path / ".rumdl.toml"
    assert rumdl_toml.is_file()
    content = rumdl_toml.read_text(encoding="utf-8")
    assert RUMDL_TOML_MARKER in content
    assert "MD013" in content


@pytest.mark.asyncio
async def test_repair_skips_rumdl_toml_when_already_configured(
    tmp_path: Path,
) -> None:
    # Arrange – .rumdl.toml exists with the disable marker
    rumdl_toml = tmp_path / ".rumdl.toml"
    _ = rumdl_toml.write_text('[global]\ndisable = ["MD013"]\n', encoding="utf-8")

    with (
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_structure",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_symlinks",
            return_value=False,
        ),
        patch(
            "cortex.structure.lifecycle.startup_repair._needs_gitignore",
            return_value=False,
        ),
    ):
        report = await repair_project_setup(tmp_path)

    assert report.rumdl_config_updated is False
    assert report.skipped is True
