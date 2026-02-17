"""Tests for discovery.tool_registry."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.discovery.tool_registry import get_known_script_names, get_known_tool_names


class TestGetKnownToolNames:
    """Tests for get_known_tool_names."""

    def test_returns_non_empty_list(self) -> None:
        """get_known_tool_names returns a non-empty list of tool names."""
        names = get_known_tool_names()
        assert isinstance(names, list)
        assert len(names) > 0
        assert all(isinstance(n, str) for n in names)

    def test_includes_manage_file_and_capture_tools(self) -> None:
        """Registry includes manage_file and script capture tools."""
        names = get_known_tool_names()
        assert "manage_file" in names
        assert "capture_session_script" in names
        assert "list_session_scripts" in names


class TestGetKnownScriptNames:
    """Tests for get_known_script_names."""

    def test_returns_empty_list_when_no_synapse_scripts_dir(self) -> None:
        """Returns empty list when .cortex/synapse/scripts/python does not exist."""
        root = Path("/nonexistent/project")
        names = get_known_script_names(root)
        assert names == []

    def test_returns_script_stems_when_synapse_scripts_exist(
        self, tmp_path: Path
    ) -> None:
        """Returns script file stems when synapse scripts directory exists."""
        scripts_dir = (
            get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "scripts" / "python"
        )
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "check_format.py").touch()
        (scripts_dir / "run_tests.py").touch()
        (scripts_dir / "_utils.py").touch()
        names = get_known_script_names(tmp_path)
        assert "check_format" in names
        assert "run_tests" in names
        assert "_utils" not in names

    def test_returns_sorted_script_names(self, tmp_path: Path) -> None:
        """Returns script names in sorted order."""
        scripts_dir = (
            get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "scripts" / "python"
        )
        scripts_dir.mkdir(parents=True)
        # Create scripts in non-alphabetical order
        (scripts_dir / "zebra.py").touch()
        (scripts_dir / "alpha.py").touch()
        (scripts_dir / "beta.py").touch()
        names = get_known_script_names(tmp_path)
        assert names == ["alpha", "beta", "zebra"]

    def test_returns_empty_list_when_scripts_dir_empty(self, tmp_path: Path) -> None:
        """Returns empty list when scripts directory exists but is empty."""
        scripts_dir = (
            get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "scripts" / "python"
        )
        scripts_dir.mkdir(parents=True)
        names = get_known_script_names(tmp_path)
        assert names == []
