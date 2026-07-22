"""Regression tests for the pipeline_handoff phase-state loss race.

Reproduces the bug reported in
``.cortex/plans/archive/Investigations/investigate-pipeline-handoff-phase-state-loss-during-long-running-subagent-calls.md``:
an orchestrator and a long-running subagent can both call into
``op_write_result``/``op_init`` for the same live pipeline session. Before
the fix, the read-modify-write cycle on ``pipeline.json`` was neither locked
nor atomic, so a "slow" writer (e.g. blocked behind a subprocess or a slow
disk) could commit a state computed from a stale read, silently discarding
phases written by a faster concurrent writer in between.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from cortex.tools.session import pipeline_handoff_io as io

_LoadOrCreateState = Callable[[Path, str, Path], dict[str, object]]


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return tmp_path


def _seed_state(pdir: Path, phases: dict[str, object]) -> Path:
    pdir.mkdir(parents=True, exist_ok=True)
    sfile = io.state_path(pdir)
    payload = {
        "session_id": "test-session",
        "pipeline": "implement",
        "started_at": "2026-07-21T07:39:25+00:00",
        "phases": phases,
    }
    _ = sfile.write_text(json.dumps(payload), encoding="utf-8")
    return sfile


def _slow_load_or_create_state(
    real_load: _LoadOrCreateState,
    first_call_seen: threading.Event,
    read_started: threading.Event,
) -> _LoadOrCreateState:
    """Wrap ``load_or_create_state`` so the first caller's read is slowed down.

    Models a subagent (or orchestrator) whose write lands after a long call,
    racing a second, faster writer for the same live pipeline.
    """

    def wrapped(state_file: Path, pipe: str, root: Path) -> dict[str, object]:
        state = real_load(state_file, pipe, root)
        if not first_call_seen.is_set():
            first_call_seen.set()
            read_started.set()
            time.sleep(0.3)
        return state

    return wrapped


class TestConcurrentPhaseWritesDoNotLosePhases:
    """Two 'clients' racing a read-modify-write on the same pipeline.json."""

    def test_slow_writer_does_not_clobber_a_faster_concurrent_writer(
        self, project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange: existing pipeline.json already has a completed "select"
        # phase, matching the reported reproduction (orchestrator wrote
        # select+code, then a slow subagent call raced a second write).
        pipeline = "implement"
        pdir = io.pipeline_dir(project_root, pipeline)
        _ = _seed_state(pdir, {"select": {"phase_status": "completed"}})
        read_started = self._install_slow_read(monkeypatch)

        thread_a, thread_b = self._start_racing_writers(
            project_root, pipeline, read_started
        )
        thread_a.join(timeout=3)
        thread_b.join(timeout=3)

        # Assert: no phase written by either client is lost, and the
        # original "select" phase (present before either client ran) also
        # survives the race.
        final_state = json.loads(io.state_path(pdir).read_text(encoding="utf-8"))
        phases = final_state["phases"]
        assert "select" in phases, f"select phase lost: {phases}"
        assert "code" in phases, f"code phase lost: {phases}"
        assert "review" in phases, f"review phase lost: {phases}"

    def _install_slow_read(self, monkeypatch: pytest.MonkeyPatch) -> threading.Event:
        """Slow down the first ``load_or_create_state`` call; return its start event."""
        read_started = threading.Event()
        first_call_seen = threading.Event()
        monkeypatch.setattr(
            io,
            "load_or_create_state",
            _slow_load_or_create_state(
                io.load_or_create_state, first_call_seen, read_started
            ),
        )
        return read_started

    def _start_racing_writers(
        self, project_root: Path, pipeline: str, read_started: threading.Event
    ) -> tuple[threading.Thread, threading.Thread]:
        """Start client A first, then client B once A's read is in flight.

        Guarantees client B's write races client A's in-flight
        read-modify-write deterministically (no scheduling flakiness).
        """

        def write_client_a() -> None:
            _ = io.op_write_result(
                project_root,
                pipeline,
                "code",
                '{"status": "completed"}',
            )

        def write_client_b() -> None:
            _ = io.op_write_result(
                project_root,
                pipeline,
                "review",
                '{"status": "completed"}',
            )

        thread_a = threading.Thread(target=write_client_a)
        thread_a.start()
        assert read_started.wait(timeout=2), "client A never started its read"
        thread_b = threading.Thread(target=write_client_b)
        thread_b.start()
        return thread_a, thread_b
