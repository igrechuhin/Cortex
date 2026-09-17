"""Tests for ``memory_wal`` MCP tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.memory.wal import (
    ToolInvocationLog,
    WalOperation,
    WalStatus,
    wal_build_tool_invocation_entry,
)
from cortex.tools.memory.wal_tool import (
    MemoryWALInput,
    MemoryWALResult,
    MemoryWalToolOp,
    handle_memory_wal_sync,
    memory_wal,
)


@pytest.fixture(autouse=True)
def isolate_wal_tool_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep public wrappers and their real telemetry inside this test's project."""
    managers: dict[str, object] = {}
    monkeypatch.setattr(
        "cortex.core.mcp_stability_usage.get_current_managers", lambda: managers
    )
    monkeypatch.setattr(
        "cortex.core.usage_context.get_current_managers", lambda: managers
    )
    monkeypatch.setattr(
        "cortex.core.usage_context.get_current_project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "cortex.core.mcp_tool_telemetry.get_current_project_root", lambda: tmp_path
    )


class WALEntryJsonFactory:
    """Minimal JSONL snippets for handler tests."""

    @staticmethod
    def error_line() -> str:
        payload = {
            "id": "a" * 12,
            "timestamp": "2026-04-15T12:00:00+00:00",
            "operation": "write",
            "file": "f.md",
            "agent_hint": "u",
            "content_hash_before": "none",
            "content_hash_after": "ab" * 8,
            "byte_delta": 1,
            "after_byte_len": 2,
            "status": "error",
            "error": "boom",
        }
        return json.dumps(payload) + "\n"

    @staticmethod
    def minimal_line(seq: int, ts: str) -> str:
        payload = {
            "id": f"{seq:012d}",
            "timestamp": ts,
            "operation": "write",
            "file": "f.md",
            "agent_hint": "u",
            "content_hash_before": "none",
            "content_hash_after": "ab" * 8,
            "byte_delta": 1,
            "after_byte_len": 2,
            "status": "ok",
            "error": None,
        }
        return json.dumps(payload)


def test_memory_wal_anomalies_handler(tmp_path: Path) -> None:
    root = tmp_path / "p"
    wal_dir = root / ".cortex" / "wal"
    wal_dir.mkdir(parents=True)
    _ = (wal_dir / "write_log.jsonl").write_text(
        WALEntryJsonFactory.error_line(),
        encoding="utf-8",
    )
    res = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.ANOMALIES),
    )
    assert res.warnings is not None
    assert any("error status" in w for w in res.warnings)


def test_memory_wal_snapshot_restore_flow(tmp_path: Path) -> None:
    root = tmp_path / "p"
    mb = root / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    _ = (mb / "z.md").write_text("orig", encoding="utf-8")
    snap_res = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.SNAPSHOT, label="L1"),
    )
    assert snap_res.snapshot_path
    _ = (mb / "z.md").write_text("changed", encoding="utf-8")
    rest = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.RESTORE, label="L1"),
    )
    assert rest.files_restored == 1
    assert (mb / "z.md").read_text(encoding="utf-8") == "orig"


def _log_two_session_entries(wal_dir: Path) -> None:
    """Seed one entry for ``current-session`` and one for ``other-session``."""
    log = ToolInvocationLog(wal_dir)
    log.log(
        wal_build_tool_invocation_entry(
            session_id="current-session",
            tool_name="run_quality_gate",
            arg_keys=[],
            status=WalStatus.OK,
            error_type=None,
        )
    )
    log.log(
        wal_build_tool_invocation_entry(
            session_id="other-session",
            tool_name="memory_wal",
            arg_keys=["operation"],
            status=WalStatus.OK,
            error_type=None,
        )
    )


def test_memory_wal_tool_invocations_returns_current_session_slice(
    tmp_path: Path,
) -> None:
    # Arrange
    root = tmp_path / "p"
    _log_two_session_entries(root / ".cortex" / "wal")

    # Act
    with patch(
        "cortex.tools.memory.wal_tool.wal_agent_hint",
        return_value="current-session",
    ):
        res = handle_memory_wal_sync(
            root,
            MemoryWALInput(operation=MemoryWalToolOp.TOOL_INVOCATIONS),
        )

    # Assert: only the current session's tool-call sequence surfaces.
    assert res.tool_invocations is not None
    assert len(res.tool_invocations) == 1
    assert res.tool_invocations[0].tool_name == "run_quality_gate"


def test_memory_wal_tool_invocations_empty_session_returns_empty_list(
    tmp_path: Path,
) -> None:
    # Arrange
    root = tmp_path / "p"

    # Act
    with patch(
        "cortex.tools.memory.wal_tool.wal_agent_hint",
        return_value="unused-session",
    ):
        res = handle_memory_wal_sync(
            root,
            MemoryWALInput(operation=MemoryWalToolOp.TOOL_INVOCATIONS),
        )

    # Assert
    assert res.tool_invocations == []


def test_memory_wal_read_last_50_cap(tmp_path: Path) -> None:
    root = tmp_path / "p"
    wal_dir = root / ".cortex" / "wal"
    wal_dir.mkdir(parents=True)
    lines = "\n".join(
        WALEntryJsonFactory.minimal_line(i, f"2026-04-15T12:{i % 60:02d}:00+00:00")
        for i in range(55)
    )
    _ = (wal_dir / "write_log.jsonl").write_text(lines + "\n", encoding="utf-8")
    res = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.READ, since=None),
    )
    assert res.entries is not None
    assert len(res.entries) == 50


class TestMemoryWalAsOf:
    """``as_of`` exposes hash-verified historical views to the analyze pipeline."""

    def test_as_of_returns_reconstructed_content(self, tmp_path: Path) -> None:
        # Arrange
        from cortex.memory.wal import MemoryWAL, WalContentFields, wal_build_entry
        from cortex.memory.wal_content import wal_encode_reverse_delta

        rel = ".cortex/memory-bank/a.md"
        payload, codec = wal_encode_reverse_delta(True, "before")
        entry = wal_build_entry(
            operation=WalOperation.WRITE,
            relative_file=rel,
            agent_hint="t",
            before_exists=True,
            before_text="before",
            after_text="after",
            status=WalStatus.OK,
            error=None,
            content_fields=WalContentFields(
                reverse_delta=payload, delta_codec=codec, step_number=4
            ),
        )
        MemoryWAL(tmp_path / ".cortex" / "wal", project_root=tmp_path).log(entry)
        # Act
        result = handle_memory_wal_sync(
            tmp_path,
            MemoryWALInput(operation=MemoryWalToolOp.AS_OF, file=rel, step_number=1),
        )
        # Assert
        assert result.as_of is not None
        assert result.as_of.content == "before"
        assert result.as_of.verified is True

    def test_as_of_requires_file_and_step_number(self, tmp_path: Path) -> None:
        # Arrange
        missing_file = MemoryWALInput(operation=MemoryWalToolOp.AS_OF, step_number=1)
        missing_step = MemoryWALInput(operation=MemoryWalToolOp.AS_OF, file="a.md")
        # Act / Assert
        with pytest.raises(ValueError, match="non-empty file"):
            _ = handle_memory_wal_sync(tmp_path, missing_file)
        with pytest.raises(ValueError, match="step_number"):
            _ = handle_memory_wal_sync(tmp_path, missing_step)


@pytest.mark.parametrize(
    "operation", [MemoryWalToolOp.SNAPSHOT, MemoryWalToolOp.RESTORE]
)
@pytest.mark.parametrize("label", ["", " ", "..", "nested/label", "nested\\label"])
def test_snapshot_handler_rejects_labels_before_creating_directories(
    tmp_path: Path, operation: MemoryWalToolOp, label: str
) -> None:
    # Arrange
    root = tmp_path / "project"
    # Act / Assert
    with pytest.raises(ValueError, match="single directory name"):
        _ = handle_memory_wal_sync(
            root, MemoryWALInput(operation=operation, label=label)
        )
    assert not root.exists()


def test_snapshot_default_label_only_applies_when_omitted(tmp_path: Path) -> None:
    # Arrange
    root = tmp_path / "project"
    # Act
    with patch(
        "cortex.tools.memory.wal_tool._default_snapshot_label", return_value="generated"
    ):
        result = handle_memory_wal_sync(
            root, MemoryWALInput(operation=MemoryWalToolOp.SNAPSHOT)
        )
    # Assert
    assert result.snapshot_path is not None
    assert Path(result.snapshot_path).name == "generated"
    assert Path(result.snapshot_path).is_dir()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["snapshot", "restore"])
@pytest.mark.parametrize("label", ["", "..", "nested/label"])
async def test_memory_wal_returns_structured_invalid_label_error(
    tmp_path: Path, operation: str, label: str
) -> None:
    # Arrange
    with patch(
        "cortex.tools.memory.wal_tool.get_or_resolve_project_root",
        new=AsyncMock(return_value=tmp_path),
    ):
        # Act
        result = await memory_wal(operation=operation, label=label)
    # Assert
    # BELIEF: The public tool response is JSON; explicit keys distinguish an error from success.
    payload = json.loads(result)
    assert payload["status"] == "error"
    assert "single directory name" in payload["error"]
    assert "snapshot_path" not in payload
    assert "files_restored" not in payload
    telemetry = ToolInvocationLog(tmp_path / ".cortex" / "wal").read()
    assert [entry.tool_name for entry in telemetry] == ["memory_wal"]


@pytest.mark.asyncio
async def test_memory_wal_returns_structured_missing_snapshot_error(
    tmp_path: Path,
) -> None:
    # Arrange
    with patch(
        "cortex.tools.memory.wal_tool.get_or_resolve_project_root",
        new=AsyncMock(return_value=tmp_path),
    ):
        # Act
        result = await memory_wal(operation="restore", label="missing")
    # Assert
    # BELIEF: The public JSON error envelope must not advertise restored files.
    payload = json.loads(result)
    assert payload["status"] == "error"
    assert "No WAL snapshot" in payload["error"]
    assert "files_restored" not in payload


@pytest.mark.asyncio
async def test_memory_wal_returns_structured_snapshot_io_error(tmp_path: Path) -> None:
    # Arrange
    with (
        patch(
            "cortex.tools.memory.wal_tool.get_or_resolve_project_root",
            new=AsyncMock(return_value=tmp_path),
        ),
        patch(
            "cortex.tools.memory.wal_tool.MemoryWAL.snapshot",
            side_effect=OSError("snapshot copy failed"),
        ),
    ):
        # Act
        result = await memory_wal(operation="snapshot", label="safe")
    # Assert
    # BELIEF: The public JSON error envelope must not advertise a created snapshot.
    payload = json.loads(result)
    assert payload["status"] == "error"
    assert payload["error"] == "snapshot copy failed"
    assert "snapshot_path" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file",
    [
        "pyproject.toml",
        "src/private.py",
        ".cortex/memory-bank/../private.md",
        ".cortex/memory-bank/file.json",
    ],
)
async def test_memory_wal_as_of_rejects_out_of_scope_files(
    tmp_path: Path, file: str
) -> None:
    # Arrange
    manifest = tmp_path / "pyproject.toml"
    _ = manifest.write_text("private-sentinel", encoding="utf-8")
    # Act
    result = await memory_wal(operation="as_of", file=file, step_number=0)
    # Assert
    # BELIEF: The public JSON envelope distinguishes rejected reads from reconstructed content.
    payload = json.loads(result)
    assert payload["status"] == "error"
    assert "private-sentinel" not in result
    assert "as_of" not in payload
    assert manifest.read_text(encoding="utf-8") == "private-sentinel"


@pytest.mark.asyncio
async def test_memory_wal_as_of_returns_missing_allowed_file(tmp_path: Path) -> None:
    # Arrange
    file = ".cortex/memory-bank/analyses/missing.md"
    # Act
    result = await memory_wal(operation="as_of", file=file, step_number=3)
    # Assert
    parsed = MemoryWALResult.model_validate_json(result)
    assert parsed.as_of is not None
    assert parsed.as_of.file == file
    assert not parsed.as_of.exists
    assert parsed.as_of.source == "current"
    assert not parsed.as_of.verified
    assert not (tmp_path / ".cortex" / "memory-bank").exists()


@pytest.mark.asyncio
async def test_memory_wal_as_of_rejects_symlinked_memory_file(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / ".cortex" / "memory-bank" / "linked.md"
    target.parent.mkdir(parents=True)
    external = tmp_path / "private.md"
    _ = external.write_text("private-sentinel", encoding="utf-8")
    target.symlink_to(external)
    # Act
    result = await memory_wal(
        operation="as_of", file=".cortex/memory-bank/linked.md", step_number=0
    )
    # Assert
    # BELIEF: The public JSON envelope must reject linked content without returning its text.
    payload = json.loads(result)
    assert payload["status"] == "error"
    assert "symlinks" in payload["error"]
    assert "private-sentinel" not in result
    assert "as_of" not in payload
