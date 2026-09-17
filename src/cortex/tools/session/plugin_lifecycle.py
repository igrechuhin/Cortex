"""Thin native hooks over existing session orientation and handoff operations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import cast

from fastmcp.exceptions import ToolError

from cortex.core.context_logging import MCPContext
from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import get_current_managers, get_or_resolve_project_root
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.tools.memory.compaction_handoff import (
    build_handoff,
    handoff_path,
    read_handoff,
    write_handoff,
)
from cortex.tools.session.plugin_hook_event import PluginHookEvent

_started: set[tuple[Path, str, str | None]] = set()


def _output(event: str, message: str) -> str:
    if event == "SessionStart":
        return json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": message[:3000],
                }
            }
        )
    return json.dumps({"systemMessage": message[:3000]})


def _event_identity(event: PluginHookEvent) -> str:
    identity = f"{event.host}:{event.session_id}:{event.trigger}:"
    # ponytail: without host event IDs, Codex collapses same-turn compactions.
    # Use native event IDs when available; fingerprints cannot prove exactly-once.
    if event.host == "codex" and event.turn_id:
        identity += event.turn_id
    else:
        if not event.transcript_path or not Path(event.transcript_path).is_absolute():
            raise ValueError("PreCompact requires an absolute existing transcript path")
        stat = Path(event.transcript_path).stat()
        identity += f"{event.transcript_path}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(identity.encode()).hexdigest()


async def _save_handoff(
    root: Path, event: PluginHookEvent, fs: FileSystemManager
) -> str:
    identity = _event_identity(event)
    previous = await read_handoff(root, fs)
    receipts = previous.hook_event_ids if previous else []
    if identity in receipts:
        return ""
    active = get_cortex_path(root, CortexResourceType.MEMORY_BANK) / "activeContext.md"
    content, _ = await fs.read_file(active)
    handoff = previous if previous else build_handoff(None, None)
    handoff.hook_snapshot = content[:2400]
    handoff.session_id = event.session_id
    handoff.hook_event_ids.append(identity)
    await write_handoff(root, handoff, fs)
    saved = await read_handoff(root, fs)
    if saved is None or identity not in saved.hook_event_ids:
        raise OSError("handoff read-back did not confirm persistence")
    return _output(
        event.event,
        "Cortex saved a bounded memory-bank handoff (not a transcript summary).",
    )


async def _precompact(root: Path, event: PluginHookEvent) -> str:
    managers = get_current_managers()
    if managers is None:
        raise RuntimeError("MCP managers unavailable")
    fs = await get_manager(cast(ManagersDict, managers), "fs", FileSystemManager)
    lock = handoff_path(root).with_suffix(".hook.lock")
    await fs.acquire_lock(lock)
    try:
        return await _save_handoff(root, event, fs)
    finally:
        await fs.release_lock(lock)


def _orientation(raw: str) -> str:
    result: object = json.loads(raw)
    if not isinstance(result, dict):
        raise RuntimeError("session orientation unavailable")
    result = cast(dict[str, object], result)
    if result.get("status") != "success":
        raise RuntimeError("session orientation unavailable")
    brief = result.get("brief")
    if not isinstance(brief, dict):
        raise ValueError("session brief missing")
    brief = cast(dict[str, object], brief)
    handoff = brief.get("last_handoff")
    if isinstance(handoff, dict):
        handoff = cast(dict[str, object], handoff)
        brief["last_handoff"] = {
            key: str(handoff[key])[:160]
            for key in ("in_progress", "blockers", "next_actions", "hook_snapshot")
            if handoff.get(key)
        }
    lines = [
        f"{key}: {str(brief[key])[:800]}"
        for key in ("current_focus", "next_work_item", "last_handoff")
        if brief.get(key)
    ]
    return (
        "\n".join(lines)
        or "Cortex workspace ready; use session() for full orientation."
    )


async def _start(root: Path, event: PluginHookEvent, ctx: MCPContext | None) -> str:
    from cortex.tools.session.start_tools import session_start

    identity = (root, event.session_id, event.source)
    if identity in _started:
        return ""
    if len(_started) >= 128:
        _started.clear()
    _started.add(identity)
    try:
        return _output(event.event, _orientation(await session_start(ctx=ctx)))
    except BaseException:
        _started.discard(identity)
        raise


async def run_plugin_hook(
    payload: dict[str, object] | None, ctx: MCPContext | None
) -> str:
    """Validate against MCP's workspace, then perform one bounded operation."""
    try:
        event = PluginHookEvent.model_validate(payload)
        async with asyncio.timeout(12):
            root = (await get_or_resolve_project_root(ctx)).resolve()
            cwd = Path(event.cwd).resolve(strict=True)
            if (
                cwd != root
                or not get_cortex_path(root, CortexResourceType.CORTEX_DIR).is_dir()
            ):
                raise ValueError(
                    "Hook cwd must match the initialized MCP workspace root"
                )
            if event.event == "SessionStart":
                return await _start(root, event, ctx)
            return await _precompact(root, event)
    except (ValueError, OSError, RuntimeError, TimeoutError) as exc:
        raise ToolError(
            f"Cortex hook failed: {str(exc)[:500]}. "
            + "Run session() explicitly; handoff was not confirmed saved."
        ) from exc
