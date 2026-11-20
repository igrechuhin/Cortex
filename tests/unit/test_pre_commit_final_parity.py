"""Verify fixed parity selection for staged-final commits."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.tools.execution import pre_commit_final_parity as parity


@pytest.mark.asyncio
async def test_no_docc_when_workflow_has_no_public_docs_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workflow = tmp_path / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    _ = workflow.write_text("jobs: {}")
    runner = MagicMock(return_value=b"")
    monkeypatch.setattr(parity, "_run", runner)
    await parity.run_staged_final_parity(tmp_path)
    assert runner.call_count == 2


@pytest.mark.asyncio
async def test_required_parity_paths_and_two_file_size_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workflow = tmp_path / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    _ = workflow.write_text("run: check_public_docs")
    swift = tmp_path / ".cortex" / "synapse" / "scripts" / "swift"
    swift.mkdir(parents=True)
    sizes = swift / "check_file_sizes.py"
    _ = sizes.touch()
    runner = MagicMock(side_effect=[b"Changed.swift\n", b"", b"", b"", b""])
    monkeypatch.setattr(parity, "_run", runner)
    monkeypatch.setenv("DOCC_PUBLIC_THRESHOLD", "42")
    await parity.run_staged_final_parity(tmp_path)
    command = [str(tmp_path / ".venv" / "bin" / "python"), str(sizes)]
    runner.assert_any_call(tmp_path, command, files="Changed.swift\n")
    runner.assert_any_call(tmp_path, command, full_scan=True)
    runner.assert_any_call(
        tmp_path,
        [
            "python3",
            str(swift / "check_public_docs.py"),
            "Sources",
            "--threshold",
            "42",
            "--quiet",
        ],
    )
