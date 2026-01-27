from pathlib import Path
from unittest.mock import patch

from cortex.structure.lifecycle.symlinks import CursorSymlinkManager
from cortex.structure.structure_config import StructureConfig


def test_setup_cursor_integration_when_disabled_returns_error_report(
    tmp_path: Path,
) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    config.structure_config["cursor_integration"] = {
        "enabled": False,
        "symlink_location": ".cursor",
        "symlinks": {"memory_bank": True, "rules": True, "plans": True},
    }
    manager = CursorSymlinkManager(config)

    # Act
    report = manager.setup_cursor_integration()

    # Assert
    assert report.success is False
    assert report.errors


def test_setup_cursor_integration_when_invalid_symlink_location_returns_error_report(
    tmp_path: Path,
) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    config.structure_config["cursor_integration"] = {
        "enabled": True,
        "symlink_location": 123,
        "symlinks": {"memory_bank": True},
    }
    manager = CursorSymlinkManager(config)

    # Act
    report = manager.setup_cursor_integration()

    # Assert
    assert report.success is False
    assert report.errors


def test_setup_cursor_integration_creates_memory_bank_symlink(tmp_path: Path) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    config.structure_config["cursor_integration"] = {
        "enabled": True,
        "symlink_location": ".cursor",
        "symlinks": {"memory_bank": True, "rules": False, "plans": False},
    }
    # Ensure target exists
    config.get_path("memory_bank").mkdir(parents=True, exist_ok=True)
    manager = CursorSymlinkManager(config)

    # Act
    report = manager.setup_cursor_integration()

    # Assert
    assert report.success is True
    link = tmp_path / ".cursor" / "memory-bank"
    assert link.is_symlink()
    assert report.symlinks_created


def test_create_symlink_when_link_is_directory_records_error(tmp_path: Path) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    manager = CursorSymlinkManager(config)

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.mkdir()  # directory blocks replacement

    created = []
    errors: list[str] = []

    # Act
    manager.create_symlink(target, link, created, errors)

    # Assert
    assert created == []
    assert any("Cannot replace directory with symlink" in e for e in errors)


def test_setup_cursor_integration_when_cursor_integration_not_dict_returns_error(
    tmp_path: Path,
) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    config.structure_config["cursor_integration"] = "not-a-dict"
    manager = CursorSymlinkManager(config)

    # Act
    report = manager.setup_cursor_integration()

    # Assert
    assert report.success is False
    assert report.errors


def test_setup_cursor_integration_when_symlinks_not_dict_returns_error(
    tmp_path: Path,
) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    config.structure_config["cursor_integration"] = {
        "enabled": True,
        "symlink_location": ".cursor",
        "symlinks": "not-a-dict",
    }
    manager = CursorSymlinkManager(config)

    # Act
    report = manager.setup_cursor_integration()

    # Assert
    assert report.success is False
    assert report.errors


def test_create_symlink_when_unlink_fails_records_error(tmp_path: Path) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    manager = CursorSymlinkManager(config)

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    _ = link.write_text("x", encoding="utf-8")

    created = []
    errors: list[str] = []

    def _raise(*_args, **_kwargs) -> None:
        raise PermissionError("nope")

    # Act
    with patch("pathlib.Path.unlink", side_effect=_raise):
        manager.create_symlink(target, link, created, errors)

    # Assert
    assert created == []
    assert any("Failed to remove existing link" in e for e in errors)


def test_create_symlink_windows_directory_uses_mklink_junction(tmp_path: Path) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    manager = CursorSymlinkManager(config)

    target = tmp_path / "target_dir"
    target.mkdir()
    link = tmp_path / "link_dir"

    created = []
    errors: list[str] = []

    with (
        patch("platform.system", return_value="Windows"),
        patch("subprocess.run") as run,
    ):
        # Act
        manager.create_symlink(target, link, created, errors)

        # Assert
        assert errors == []
        assert created
        run.assert_called()
        args = run.call_args[0][0]
        assert args[:3] == ["cmd", "/c", "mklink"]
        assert "/J" in args


def test_create_symlink_windows_file_uses_mklink_file(tmp_path: Path) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    manager = CursorSymlinkManager(config)

    target = tmp_path / "target_file.txt"
    _ = target.write_text("x", encoding="utf-8")
    link = tmp_path / "link_file.txt"

    created = []
    errors: list[str] = []

    with (
        patch("platform.system", return_value="Windows"),
        patch("subprocess.run") as run,
    ):
        # Act
        manager.create_symlink(target, link, created, errors)

        # Assert
        assert errors == []
        assert created
        args = run.call_args[0][0]
        assert args[:3] == ["cmd", "/c", "mklink"]
        assert "/J" not in args


def test_setup_cursor_integration_when_validation_has_no_dict_error_response_returns_generic_error(  # noqa: E501
    tmp_path: Path,
) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    manager = CursorSymlinkManager(config)

    with patch.object(
        manager,
        "_validate_cursor_integration_config",
        return_value={"valid": False, "error_response": "not-a-dict"},
    ):
        # Act
        report = manager.setup_cursor_integration()

    # Assert
    assert report.success is False
    assert "Invalid cursor integration configuration" in report.errors[0]


def test_setup_cursor_integration_creates_rules_symlink(tmp_path: Path) -> None:
    # Arrange
    config = StructureConfig(tmp_path)
    config.structure_config["cursor_integration"] = {
        "enabled": True,
        "symlink_location": ".cursor",
        "symlinks": {"memory_bank": False, "rules": True, "plans": False},
    }
    config.get_path("rules").mkdir(parents=True, exist_ok=True)
    manager = CursorSymlinkManager(config)

    # Act
    report = manager.setup_cursor_integration()

    # Assert
    assert report.success is True
    link = tmp_path / ".cursor" / "rules"
    assert link.is_symlink()
    assert report.symlinks_created
