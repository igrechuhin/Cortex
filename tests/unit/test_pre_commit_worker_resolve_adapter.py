"""Tests for detached worker language resolution and quality-gate envelopes."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.tools.execution import pre_commit_worker as worker
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

    def test_error_when_no_language_detected(self, tmp_path: Path) -> None:
        """No markers anywhere up the tree yields an error dict, not an adapter."""
        with patch(
            "cortex.tools.execution.pre_commit_helpers_language.detect_language_at_path",
            return_value=None,
        ):
            resolved = resolve_adapter_worker(str(tmp_path))
        assert isinstance(resolved, dict)
        assert resolved["status"] == "error"
        assert "Could not detect project language" in str(resolved["error"])

    def test_error_for_unsupported_language(self, tmp_path: Path) -> None:
        """A detected language with no registered adapter yields an error dict."""
        from cortex.services.language_detector import LanguageInfo

        haskell_info = LanguageInfo(
            language="haskell",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.5,
        )
        with patch(
            "cortex.tools.execution.pre_commit_helpers_language.detect_or_use_language",
            return_value=(haskell_info, str(tmp_path)),
        ):
            resolved = resolve_adapter_worker(str(tmp_path))
        assert isinstance(resolved, dict)
        assert resolved["status"] == "error"
        assert resolved["error"] == "Unsupported language: haskell"


def test_delivered_marker_is_not_restamped_from_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    result_path = tmp_path / "result.json"
    delivered: dict[str, object] = {
        "status": "completed",
        "quality_gate_pending": False,
    }
    monkeypatch.setattr(sys, "argv", ["worker", "--quality-gate"])

    # Act
    worker.atomic_write(result_path, delivered)

    # Assert
    assert json.loads(result_path.read_text())["quality_gate_pending"] is False
    assert delivered["quality_gate_pending"] is False


def _set_worker_argv(monkeypatch: pytest.MonkeyPatch, result_path: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker",
            "--quality-gate",
            "--result-file",
            str(result_path),
            "--project-root",
            str(result_path.parent),
        ],
    )


@pytest.mark.parametrize("outcome", ["success", "ignored", "blocked", "error"])
def test_quality_gate_marker_survives_terminal_worker_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    # Arrange
    result_path = tmp_path / "result.json"
    _set_worker_argv(monkeypatch, result_path)

    def check_staging(_root: Path) -> list[str]:
        assert json.loads(result_path.read_text())["quality_gate_pending"] is True
        monkeypatch.setattr(sys, "argv", ["worker"])
        return ["ignored.py"] if outcome == "ignored" else []

    with (
        patch.object(worker, "check_staged_gitignored", side_effect=check_staging),
        patch.object(
            worker,
            "precommit_block_response",
            return_value={"status": "error"} if outcome == "blocked" else None,
        ),
        patch.object(
            worker,
            "_run_checks",
            return_value={"status": "success"},
            side_effect=RuntimeError("worker failed") if outcome == "error" else None,
        ),
    ):
        # Act
        if outcome == "error":
            with pytest.raises(SystemExit, match="1"):
                worker.main()
        else:
            worker.main()

    # Assert
    envelope = json.loads(result_path.read_text())
    assert envelope["quality_gate_pending"] is True
    assert envelope["status"] == ("error" if outcome == "error" else "completed")
