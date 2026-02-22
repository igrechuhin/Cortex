"""Tests for cortex.discovery.tool_registry."""

from pathlib import Path

from cortex.discovery.tool_registry import get_known_script_names, get_known_tool_names


class TestGetKnownToolNames:
    """Tests for get_known_tool_names."""

    def test_returns_list(self) -> None:
        """Returns a list of strings."""
        result = get_known_tool_names()
        assert isinstance(result, list)
        assert all(isinstance(x, str) for x in result)

    def test_contains_expected_tools(self) -> None:
        """List includes core tools used by discovery."""
        names = get_known_tool_names()
        assert "manage_file" in names
        assert "load_context" in names
        assert "execute_pre_commit_checks" in names

    def test_no_duplicates(self) -> None:
        """No duplicate tool names."""
        names = get_known_tool_names()
        assert len(names) == len(set(names))

    def test_all_non_empty(self) -> None:
        """Every name is non-empty."""
        names = get_known_tool_names()
        assert all(len(n) > 0 for n in names)


class TestGetKnownScriptNames:
    """Tests for get_known_script_names (file scanning)."""

    def test_missing_synapse_scripts_dir_returns_empty(self, tmp_path: Path) -> None:
        """When .cortex/synapse/scripts/python does not exist, returns []."""
        # tmp_path is project root; no .cortex/synapse created
        result = get_known_script_names(tmp_path)
        assert result == []

    def test_empty_scripts_dir_returns_empty(self, tmp_path: Path) -> None:
        """When scripts dir exists but has no .py files, returns []."""
        scripts_dir = tmp_path / ".cortex" / "synapse" / "scripts" / "python"
        scripts_dir.mkdir(parents=True)
        result = get_known_script_names(tmp_path)
        assert result == []

    def test_skips_private_modules(self, tmp_path: Path) -> None:
        """Scripts whose name starts with _ are excluded."""
        scripts_dir = tmp_path / ".cortex" / "synapse" / "scripts" / "python"
        scripts_dir.mkdir(parents=True)
        _ = (scripts_dir / "_internal.py").write_text("# private")
        _ = (scripts_dir / "run_tests.py").write_text("# public")
        result = get_known_script_names(tmp_path)
        assert result == ["run_tests"]

    def test_returns_stems_sorted(self, tmp_path: Path) -> None:
        """Returns file stems (no .py) in sorted order."""
        scripts_dir = tmp_path / ".cortex" / "synapse" / "scripts" / "python"
        scripts_dir.mkdir(parents=True)
        _ = (scripts_dir / "z_last.py").write_text("")
        _ = (scripts_dir / "a_first.py").write_text("")
        _ = (scripts_dir / "m_mid.py").write_text("")
        result = get_known_script_names(tmp_path)
        assert result == ["a_first", "m_mid", "z_last"]

    def test_multiple_scripts(self, tmp_path: Path) -> None:
        """Multiple public scripts are all returned."""
        scripts_dir = tmp_path / ".cortex" / "synapse" / "scripts" / "python"
        scripts_dir.mkdir(parents=True)
        for name in ["format", "lint", "type_check"]:
            _ = (scripts_dir / f"{name}.py").write_text("")
        result = get_known_script_names(tmp_path)
        assert set(result) == {"format", "lint", "type_check"}
        assert len(result) == 3
