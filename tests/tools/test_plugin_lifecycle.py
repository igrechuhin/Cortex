"""Behavioral contracts for native lifecycle handoffs."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cortex.core.file_system import FileSystemManager
from cortex.core.usage_context import (
    get_current_managers,
    get_current_project_root,
    set_current_managers,
    set_current_project_root,
)
from cortex.tools.memory.compaction_handoff import read_handoff, write_handoff
from cortex.tools.session import plugin_lifecycle as hooks
from cortex.tools.session.models import InProgressTask, SessionHandoff
from cortex.tools.session.plugin_hook_event import PluginHookEvent


def _workspace(path: Path) -> FileSystemManager:
    memory = path / ".cortex/memory-bank"
    memory.mkdir(parents=True)
    _ = (memory / "activeContext.md").write_text(f"Continue work in {path.name}")
    return FileSystemManager(path)


def _event(root: Path, turn: str = "turn-1") -> PluginHookEvent:
    return PluginHookEvent(
        host="codex",
        event="PreCompact",
        cwd=str(root),
        session_id="session-1",
        trigger="auto",
        turn_id=turn,
    )


async def _run(event: PluginHookEvent, fs: FileSystemManager) -> str:
    previous_root, previous_managers = (
        get_current_project_root(),
        get_current_managers(),
    )
    set_current_project_root(Path(event.cwd))
    set_current_managers({"fs": fs})
    try:
        return await hooks.run_plugin_hook(event.model_dump(), None)
    finally:
        set_current_project_root(previous_root)
        set_current_managers(previous_managers)


def _startup_event(root: Path) -> PluginHookEvent:
    return PluginHookEvent(
        host="claude",
        event="SessionStart",
        cwd=str(root),
        session_id="startup",
        source="startup",
    )


@pytest.mark.asyncio
async def test_replay_after_other_event_preserves_handoff(tmp_path: Path) -> None:
    fs = _workspace(tmp_path)
    _ = await _run(_event(tmp_path), fs)
    _ = await _run(_event(tmp_path, "turn-2"), fs)
    before = await read_handoff(tmp_path, fs)

    result = await _run(_event(tmp_path), fs)

    assert result == ""
    assert await read_handoff(tmp_path, fs) == before
    assert before is not None and before.hook_snapshot is not None
    assert "Continue work" in before.hook_snapshot


@pytest.mark.asyncio
async def test_concurrent_roots_with_spaces_are_isolated(tmp_path: Path) -> None:
    roots = [tmp_path / "project one", tmp_path / "project two"]
    filesystems = [_workspace(root) for root in roots]

    _ = await asyncio.gather(
        *(_run(_event(root), fs) for root, fs in zip(roots, filesystems, strict=True))
    )

    for root, fs in zip(roots, filesystems, strict=True):
        handoff = await read_handoff(root, fs)
        assert handoff is not None
        assert handoff.hook_snapshot is not None
        assert root.name in handoff.hook_snapshot


@pytest.mark.asyncio
async def test_persistence_failure_never_reports_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fs = _workspace(tmp_path)
    monkeypatch.setattr(
        hooks, "get_or_resolve_project_root", AsyncMock(return_value=tmp_path)
    )
    monkeypatch.setattr(hooks, "get_current_managers", lambda: {"fs": fs})
    monkeypatch.setattr(
        hooks, "write_handoff", AsyncMock(side_effect=OSError("disk full"))
    )

    with pytest.raises(ToolError, match="disk full"):
        _ = await hooks.run_plugin_hook(_event(tmp_path).model_dump(), None)
    assert await read_handoff(tmp_path, fs) is None


@pytest.mark.asyncio
async def test_workspace_mismatch_does_not_mutate_other_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "mcp"
    fs = _workspace(root)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr(
        hooks, "get_or_resolve_project_root", AsyncMock(return_value=root)
    )

    with pytest.raises(ToolError):
        _ = await hooks.run_plugin_hook(_event(other).model_dump(), None)
    assert await read_handoff(root, fs) is None
    assert not (other / ".cortex").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {}, {"event": "Stop"}])
async def test_malformed_event_returns_visible_diagnostic(
    payload: dict[str, object] | None,
) -> None:
    server = FastMCP("hook-errors")

    async def invoke(payload: dict[str, object] | None) -> str:
        return await hooks.run_plugin_hook(payload, None)

    _ = server.tool(invoke)

    async with Client(server) as client:
        result = await client.call_tool(
            "invoke", {"payload": payload}, raise_on_error=False
        )

    assert result.is_error


@pytest.mark.asyncio
async def test_missing_mcp_managers_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _workspace(tmp_path)
    monkeypatch.setattr(
        hooks, "get_or_resolve_project_root", AsyncMock(return_value=tmp_path)
    )
    monkeypatch.setattr(hooks, "get_current_managers", lambda: None)

    with pytest.raises(ToolError):
        _ = await hooks.run_plugin_hook(_event(tmp_path).model_dump(), None)


@pytest.mark.asyncio
async def test_hook_preserves_structured_continuation(tmp_path: Path) -> None:
    fs = _workspace(tmp_path)
    original = SessionHandoff(
        session_id="previous",
        completed_tasks=["Finished analysis"],
        in_progress=InProgressTask(task="Plugin verification", notes="Do not commit"),
        blockers=["Host credentials"],
        decisions_made=["Preserve settings"],
        next_actions=["Authenticate host"],
    )
    await write_handoff(tmp_path, original, fs)

    _ = await _run(_event(tmp_path), fs)

    saved = await read_handoff(tmp_path, fs)
    assert saved is not None
    for field in (
        "completed_tasks",
        "in_progress",
        "blockers",
        "decisions_made",
        "next_actions",
    ):
        assert getattr(saved, field) == getattr(original, field)
    assert saved.hook_snapshot == f"Continue work in {tmp_path.name}"


def _startup_response() -> str:
    return json.dumps(
        {
            "status": "success",
            "brief": {
                "current_focus": "x" * 5000,
                "next_work_item": "Verify plugin",
                "last_handoff": {
                    "hook_event_ids": ["receipt" * 10] * 100,
                    "next_actions": ["Resume regression"],
                    "hook_snapshot": "Saved continuation",
                },
            },
        }
    )


@pytest.mark.asyncio
async def test_startup_duplicate_and_failure_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _workspace(tmp_path)
    monkeypatch.setattr(
        hooks, "get_or_resolve_project_root", AsyncMock(return_value=tmp_path)
    )
    start = AsyncMock(
        side_effect=[
            RuntimeError("temporarily unavailable"),
            _startup_response(),
        ]
    )
    monkeypatch.setattr("cortex.tools.session.start_tools.session_start", start)
    event = _startup_event(tmp_path).model_dump()

    with pytest.raises(ToolError, match="temporarily unavailable"):
        _ = await hooks.run_plugin_hook(event, None)
    first, duplicate = await asyncio.gather(
        hooks.run_plugin_hook(event, None), hooks.run_plugin_hook(event, None)
    )

    assert duplicate == ""
    context = json.loads(first)["hookSpecificOutput"]["additionalContext"]
    assert len(context) <= 3000 and "Verify plugin" in context
    assert "Resume regression" in context
    assert "Saved continuation" in context


@pytest.mark.asyncio
async def test_readback_failure_never_claims_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fs = _workspace(tmp_path)
    monkeypatch.setattr(
        hooks, "get_or_resolve_project_root", AsyncMock(return_value=tmp_path)
    )
    monkeypatch.setattr(hooks, "get_current_managers", lambda: {"fs": fs})
    monkeypatch.setattr(hooks, "write_handoff", AsyncMock())

    with pytest.raises(ToolError):
        _ = await hooks.run_plugin_hook(_event(tmp_path).model_dump(), None)
    assert await read_handoff(tmp_path, fs) is None


@pytest.mark.asyncio
async def test_claude_replay_uses_transcript_identity(tmp_path: Path) -> None:
    fs = _workspace(tmp_path)
    transcript = tmp_path / "transcript.jsonl"
    _ = transcript.write_text('{"turn": 1}\n')
    event = PluginHookEvent(
        host="claude",
        event="PreCompact",
        cwd=str(tmp_path),
        session_id="claude",
        trigger="manual",
        transcript_path=str(transcript),
    )

    first = await _run(event, fs)
    duplicate = await _run(event, fs)

    assert "saved" in first and duplicate == ""
    handoff = await read_handoff(tmp_path, fs)
    assert handoff is not None and len(handoff.hook_event_ids) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"cwd": "relative"},
        {"trigger": None},
        {"host": "claude", "turn_id": None},
        {"event": "SessionStart", "source": None},
    ],
)
async def test_incomplete_event_does_not_write_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object]
) -> None:
    fs = _workspace(tmp_path)
    monkeypatch.setattr(
        hooks, "get_or_resolve_project_root", AsyncMock(return_value=tmp_path)
    )
    monkeypatch.setattr(hooks, "get_current_managers", lambda: {"fs": fs})

    with pytest.raises(ToolError):
        _ = await hooks.run_plugin_hook(_event(tmp_path).model_dump() | changes, None)
    assert await read_handoff(tmp_path, fs) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response", ["[]", '{"status":"error"}', '{"status":"success"}']
)
async def test_startup_rejects_failed_orientation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: str
) -> None:
    _ = _workspace(tmp_path)
    monkeypatch.setattr(
        hooks, "get_or_resolve_project_root", AsyncMock(return_value=tmp_path)
    )
    monkeypatch.setattr(
        "cortex.tools.session.start_tools.session_start",
        AsyncMock(return_value=response),
    )
    event = _startup_event(tmp_path)

    with pytest.raises(ToolError):
        _ = await hooks.run_plugin_hook(event.model_dump(), None)
