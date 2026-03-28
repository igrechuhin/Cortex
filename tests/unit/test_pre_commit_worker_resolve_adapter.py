"""Tests for detached worker language resolution (run_quality_gate path)."""

from pathlib import Path

from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.tools.execution.pre_commit_worker import resolve_adapter_worker


class TestResolveAdapterWorker:
    """resolve_adapter_worker matches Phase A zero-arg quality gate routing."""

    def test_selects_swift_adapter_for_package_swift(self, tmp_path: Path) -> None:
        """SwiftPM marker yields SwiftAdapter (not Python synapse scripts)."""
        _ = (tmp_path / "Package.swift").write_text(
            "// swift-tools-version:5.9\n",
            encoding="utf-8",
        )
        resolved = resolve_adapter_worker(str(tmp_path))
        assert not isinstance(resolved, dict)
        adapter, info = resolved
        assert isinstance(adapter, SwiftAdapter)
        assert info.language == "swift"

    def test_selects_python_adapter_for_pyproject(self, tmp_path: Path) -> None:
        """Python marker yields PythonAdapter."""
        _ = (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "t"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        resolved = resolve_adapter_worker(str(tmp_path))
        assert not isinstance(resolved, dict)
        adapter, info = resolved
        assert isinstance(adapter, PythonAdapter)
        assert info.language == "python"
