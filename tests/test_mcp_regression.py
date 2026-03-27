import asyncio
import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.project_root_resolver import (
    clear_cached_root,
    resolve_project_root_async,
)
from cortex.core.usage_context import (
    set_current_managers,
    set_current_project_root,
)
from cortex.tools.session.pipeline_handoff import pipeline_handoff


class _Root:
    def __init__(self, uri: str) -> None:
        self.uri = uri


class _RootsResult:
    def __init__(self, roots: list[_Root]) -> None:
        self.roots = roots


@pytest.mark.asyncio
async def test_concurrent_tool_calls_saturation_does_not_trigger_roots_list_disconnects(
    temp_project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent: concurrent tool saturation crashing MCP via simultaneous `roots/list` requests."""
    # Ensure the root resolver cache is cold so concurrent tool calls must
    # contend for list_roots() if the synchronization is broken.
    clear_cached_root()
    monkeypatch.delenv("CORTEX_USE_FALLBACK_ROOT", raising=False)
    set_current_managers(None)
    set_current_project_root(None)

    list_roots_call_count = 0
    list_roots_in_progress = 0

    async def list_roots() -> _RootsResult:
        nonlocal list_roots_call_count, list_roots_in_progress
        list_roots_call_count += 1
        list_roots_in_progress += 1
        assert (
            list_roots_in_progress == 1
        ), "list_roots() overlapped; per-process cache/lock regression detected"
        try:
            # Ensure any concurrent list_roots invocation overlaps at least
            # once (if the protection regresses) for deterministic detection.
            await asyncio.sleep(0)
            uri = f"file://{temp_project_root}"
            return _RootsResult(roots=[_Root(uri=uri)])
        finally:
            list_roots_in_progress -= 1

    # Minimal MCP Context mock:
    # - roots capability: True
    # - list_roots: controlled async function
    # - ctx.log: avoid log_client failures inside tool calls
    ctx = MagicMock()
    session = MagicMock()
    session.check_client_capability = MagicMock(return_value=True)
    session.list_roots = AsyncMock(side_effect=list_roots)
    ctx.session = session
    ctx.log = AsyncMock()

    # Tool init (usage_context) would normally construct managers; it's
    # irrelevant for root-resolution regression so we short-circuit.
    with (
        patch(
            "cortex.managers.initialization.get_managers",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        coros = [
            pipeline_handoff(
                operation="read_state",
                pipeline="implement",
                ctx=ctx,
            )
            for _ in range(6)
        ]

        results = cast(
            list[str],
            await asyncio.wait_for(asyncio.gather(*coros), timeout=10.0),
        )

    assert list_roots_call_count == 1
    for r in results:
        parsed = json.loads(r)
        assert parsed["status"] in {"not_found", "error"}


@pytest.mark.asyncio
async def test_pipeline_handoff_serialization_roundtrip_string_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent: `pipeline_handoff` write/read rejecting JSON *string* payloads."""
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        AsyncMock(return_value=str(tmp_path)),
    )

    init_r = json.loads(await pipeline_handoff(operation="init", pipeline="implement"))
    assert init_r["status"] == "ok"

    await pipeline_handoff(
        operation="write_task",
        pipeline="implement",
        phase="code",
        data='{"status":"complete","value":"abc","n":1}',
    )
    task_r = json.loads(
        await pipeline_handoff(
            operation="read_task",
            pipeline="implement",
            phase="code",
        )
    )
    assert task_r["phase"] == "code"
    assert task_r["status"] == "complete"
    assert task_r["value"] == "abc"
    assert task_r["n"] == 1


@pytest.mark.asyncio
async def test_pipeline_handoff_serialization_roundtrip_object_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent: `pipeline_handoff` write/read mishandling JSON *object* payloads."""
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        AsyncMock(return_value=str(tmp_path)),
    )

    init_r = json.loads(await pipeline_handoff(operation="init", pipeline="implement"))
    assert init_r["status"] == "ok"

    payload = {"status": "passed", "coverage": 0.99, "snapshot_ref": "deadbeef"}
    await pipeline_handoff(
        operation="write_task",
        pipeline="implement",
        phase="code",
        data=payload,  # native object payload (LLM -> MCP bridge)
    )  # type: ignore[arg-type]

    task_r = json.loads(
        await pipeline_handoff(
            operation="read_task",
            pipeline="implement",
            phase="code",
        )
    )
    assert task_r["phase"] == "code"
    assert task_r["status"] == "passed"
    assert task_r["coverage"] == 0.99
    assert task_r["snapshot_ref"] == "deadbeef"


@pytest.mark.asyncio
async def test_project_root_resolution_uvx_like_uses_roots_list_instead_of_cwd(
    temp_project_root: Path,
    tmp_path: Path,
) -> None:
    """Prevent: uvx-like runner launching Cortex from the wrong CWD."""
    correct_root = temp_project_root.resolve()
    wrong_root = tmp_path.resolve() / "wrong_root"
    wrong_root.mkdir(parents=True, exist_ok=True)

    # Local run: ctx=None, so we must use fallback `get_project_root()` (cwd/script).
    clear_cached_root()
    with patch(
        "cortex.core.project_root_resolver.get_project_root",
        return_value=correct_root,
    ):
        local_resolved = await resolve_project_root_async(None, None)
        assert local_resolved == correct_root

    # uvx-like run: ctx has roots/list; even if fallback would be wrong,
    # list_roots() must win.
    clear_cached_root()
    with (
        patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=wrong_root,
        ),
    ):
        ctx = MagicMock()
        session = MagicMock()
        session.check_client_capability = MagicMock(return_value=True)
        session.list_roots = AsyncMock(
            return_value=_RootsResult(roots=[_Root(uri=f"file://{correct_root}")])
        )
        ctx.session = session

        resolved = await resolve_project_root_async(None, ctx)
        assert resolved == correct_root


@pytest.mark.asyncio
async def test_project_root_resolution_missing_list_roots_degrades_to_fallback(
    tmp_path: Path,
) -> None:
    """Prevent: missing `list_roots` capability crashing project-root resolution."""
    fallback_root = tmp_path.resolve() / "fallback_root"
    fallback_root.mkdir(parents=True, exist_ok=True)

    clear_cached_root()
    with (
        patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=fallback_root,
        ),
    ):
        # Client doesn't advertise roots capability => resolver must not touch
        # session.list_roots() and must fall back cleanly.
        ctx = MagicMock()
        session = MagicMock()
        session.check_client_capability = MagicMock(return_value=False)
        ctx.session = session

        resolved = await resolve_project_root_async(None, ctx)
        assert resolved == fallback_root


@pytest.mark.asyncio
async def test_phase_a_prompt_execution_is_serialized_by_lock(tmp_path: Path) -> None:
    """Prevent: concurrent Phase-A quality/fix prompt execution overlapping and crashing MCP server."""
    from cortex.tools.execution.pre_commit_zero_arg_tools import run_quality_gate

    set_current_managers({})
    set_current_project_root(tmp_path)

    poll_started = asyncio.Event()
    allow_first_to_finish = asyncio.Event()
    poll_second_started = asyncio.Event()

    poll_calls = 0

    async def fake_poll_phase_a_result(
        *args: object, **kwargs: object
    ) -> dict[str, object]:
        nonlocal poll_calls
        poll_calls += 1
        if poll_calls == 1:
            _ = poll_started.set()
            _ = await allow_first_to_finish.wait()
            return {"status": "ok", "preflight_passed": True}
        _ = poll_second_started.set()
        return {"status": "ok", "preflight_passed": True}

    with (
        patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools._read_pipeline_phase_config",
            return_value={"coverage_threshold": 0.90, "test_timeout": 1},
        ),
        patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools._start_phase_a_job",
            return_value={"job_id": "job-1", "status": "ok"},
        ),
        patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.poll_phase_a_result",
            new=fake_poll_phase_a_result,
        ),
    ):
        group = asyncio.gather(run_quality_gate(), run_quality_gate())

        _ = await asyncio.wait_for(poll_started.wait(), timeout=2.0)
        assert poll_calls == 1
        assert not poll_second_started.is_set()

        _ = allow_first_to_finish.set()
        _ = await asyncio.wait_for(group, timeout=5.0)

    assert poll_calls == 2
