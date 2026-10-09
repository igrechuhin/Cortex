"""Regression tests: per-connection pipeline run ids for concurrent pipelines.

Root cause: every MCP server process in a project resolved ONE shared
pipeline session id from ``.cortex/.session/.active-session.json``, so
sibling sessions running ``/cortex`` pipelines interleaved phase events in
a single run window — ``resume`` could attach a live sibling's run and
phase/task files collided under ``.cortex/.session/{id}/{pipeline}/``.

The fix (see ``cortex.tools.session.pipeline_handoff_session``) gives each
connection its own run id and makes restart-resume explicit: a fresh
process mints a new id unless it can adopt a dead-owned incomplete run via
the run-ownership registry (``.cortex/.session/.pipeline-runs.json``).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator, cast

import pytest

# AI: wrapper factories are deliberately object-typed: importing the
# cortex.experience annotation types at module level lets formatters
# reorder them ahead of cortex.tools, tripping the known package-init
# cycle on standalone collection. Runtime imports stay function-local.
from cortex.tools.session.pipeline_handoff_clock import now_iso
from cortex.tools.session.pipeline_handoff_io import (
    op_clear,
    op_init,
    op_write_result,
)
from cortex.tools.session.pipeline_handoff_resume import op_resume
from cortex.tools.session.pipeline_handoff_session import (
    get_session_id,
    live_sibling_owner_ids,
)
from cortex.tools.session.start_tools import scan_incomplete_pipeline_entries

_ENV_KEY = "CORTEX_PIPELINE_SESSION_ID"
_AGENT_ENV_KEY = "CORTEX_SESSION_ID"
_REGISTRY_RELATIVE = ".cortex/.session/.pipeline-runs.json"

# Child that inits (optionally completes one phase), reports its run id via
# a ready file, and — when given a gate path — stays alive until released,
# simulating a live sibling connection.
_CHILD_RUN_SCRIPT = (
    "import json, sys, time\n"
    "from pathlib import Path\n"
    "from cortex.tools.session.pipeline_handoff_io import op_init, op_write_result\n"
    "root, ready = (Path(a) for a in sys.argv[1:3])\n"
    "result = json.loads(op_init(root, 'implement', None))\n"
    "if len(sys.argv) > 3:\n"
    "    op_write_result(root, 'implement', 'select', '{\"status\": \"complete\"}')\n"
    "ready.write_text(result['session_id'])\n"
    "if len(sys.argv) > 3:\n"
    "    gate = Path(sys.argv[3])\n"
    "    deadline = time.monotonic() + 30\n"
    "    while not gate.exists() and time.monotonic() < deadline:\n"
    "        time.sleep(0.01)\n"
)

# Fresh process with no env id: init then resume, reporting both.
_CHILD_RESUME_SCRIPT = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "from cortex.tools.session.pipeline_handoff_io import op_init\n"
    "from cortex.tools.session.pipeline_handoff_resume import op_resume\n"
    "root, out = (Path(a) for a in sys.argv[1:3])\n"
    "init = json.loads(op_init(root, 'implement', None))\n"
    "plan = json.loads(op_resume(root, 'implement'))\n"
    "out.write_text(json.dumps({\n"
    "    'session_id': init['session_id'],\n"
    "    'resumable': plan['resumable'],\n"
    "    'plan_session_id': plan.get('session_id'),\n"
    "    'completed_phases': plan.get('completed_phases'),\n"
    "}))\n"
)


@pytest.fixture(autouse=True)
def pipeline_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Simulate a fresh process on both ends; keep recording at its default."""
    saved = os.environ.get(_ENV_KEY)
    _ = os.environ.pop(_ENV_KEY, None)
    monkeypatch.delenv("CORTEX_EXPERIENCE_RECORDING", raising=False)
    yield
    if saved is None:
        _ = os.environ.pop(_ENV_KEY, None)
    else:
        os.environ[_ENV_KEY] = saved


def _reset_pipeline_env() -> None:
    """Drop the env id get_session_id latches directly into os.environ."""
    _ = os.environ.pop(_ENV_KEY, None)


def _registry_path(root: Path) -> Path:
    return root / _REGISTRY_RELATIVE


def _entry(
    owner_pids: list[int], *, updated_at: str | None = None
) -> dict[str, object]:
    """Registry entry on this host, matching the production format."""
    stamp = updated_at if updated_at is not None else now_iso()
    return {
        "owners": [{"pid": pid, "host": platform.node()} for pid in owner_pids],
        "updated_at": stamp,
    }


def _read_registry(root: Path) -> dict[str, dict[str, object]]:
    raw: object = json.loads(_registry_path(root).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    entries = cast(dict[str, object], raw)
    return {
        str(key): cast(dict[str, object], value)
        for key, value in entries.items()
        if isinstance(value, dict)
    }


def _write_registry(root: Path, payload: dict[str, dict[str, object]]) -> None:
    path = _registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _dead_pid() -> int:
    """A pid that certainly belonged to a process that has exited."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    _ = proc.wait(timeout=30)
    return proc.pid


@contextmanager
def _live_foreign_pid() -> Iterator[int]:
    """A pid owned by a live unrelated process (a live sibling stand-in)."""
    proc = subprocess.Popen(["sleep", "60"])
    try:
        yield proc.pid
    finally:
        proc.terminate()
        _ = proc.wait(timeout=30)


def _child_env() -> dict[str, str]:
    env = {**os.environ}
    for key in (_ENV_KEY, _AGENT_ENV_KEY, "CORTEX_EXPERIENCE_RECORDING"):
        _ = env.pop(key, None)
    return env


def _wait_for_file(path: Path, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert path.exists(), f"timed out waiting for {path}"


def _spawn_runner(
    root: Path, ready: Path, gate: Path | None
) -> subprocess.Popen[bytes]:
    argv = [sys.executable, "-c", _CHILD_RUN_SCRIPT, str(root), str(ready)]
    if gate is not None:
        argv.append(str(gate))
    return subprocess.Popen(
        argv, env=_child_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def _record_running_phase(root: Path, run_id: str, pipeline: str = "implement") -> None:
    """Seed one incomplete store run (lazy import keeps collection cycle-free)."""
    # AI: importing cortex.experience.recorder before any cortex.tools
    # module trips a pre-existing package cycle; cortex.tools is imported
    # first at module scope, so the lazy import here is always safe.
    from cortex.experience.recorder import record_phase_event

    _ = record_phase_event(root, run_id, pipeline, "select", "running", enabled=True)


def _incomplete_run_owners(root: Path) -> set[str]:
    """Owners of the store's fresh incomplete runs (lazy import, see above)."""
    from cortex.experience.resume import scan_incomplete_runs

    return {run.owner for run in scan_incomplete_runs(root) if run.owner}


def _hours_ago(hours: float) -> str:
    """ISO timestamp the given number of hours in the past (within TTL)."""
    moment = datetime.now(UTC) - timedelta(hours=hours)
    return moment.isoformat(timespec="seconds")


def _state_phases(root: Path, run_id: str) -> dict[str, object]:
    state_file = root / ".cortex" / ".session" / run_id / "implement" / "pipeline.json"
    raw: object = json.loads(state_file.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    phases = cast(dict[str, object], raw).get("phases")
    assert isinstance(phases, dict)
    return cast(dict[str, object], phases)


def _run_fresh_resume_child(root: Path) -> dict[str, object]:
    """Spawn a fresh no-env process running init + resume; return its report."""
    out = root / "resume-out.json"
    child = subprocess.Popen(
        [sys.executable, "-c", _CHILD_RESUME_SCRIPT, str(root), str(out)],
        env=_child_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _ = child.wait(timeout=60)
    _wait_for_file(out)
    return cast(dict[str, object], json.loads(out.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Concurrent init across real processes
# ---------------------------------------------------------------------------


def test_concurrent_init_processes_get_distinct_run_ids(tmp_path: Path) -> None:
    """Live sibling + own init + second child never share a run window."""
    # Arrange: child A inits, completes "select", and stays alive (gate held).
    ready_a = tmp_path / "ready-a.json"
    gate_a = tmp_path / "gate-a.json"
    child_a = _spawn_runner(tmp_path, ready_a, gate_a)
    try:
        _wait_for_file(ready_a)
        sibling_id = ready_a.read_text(encoding="utf-8").strip()

        # Act: this process inits while the sibling is still live.
        own_id = json.loads(op_init(tmp_path, "implement", None))["session_id"]

        # Assert: distinct run ids, distinct state files, no shared window.
        assert own_id != sibling_id
        assert "select" in _state_phases(tmp_path, sibling_id)
        assert _state_phases(tmp_path, own_id) == {}
        assert live_sibling_owner_ids(tmp_path) == {sibling_id}

        # Act: a second child inits concurrently with the live sibling.
        ready_b = tmp_path / "ready-b.json"
        child_b = _spawn_runner(tmp_path, ready_b, None)
        _ = child_b.wait(timeout=60)
        _wait_for_file(ready_b)
        second_id = ready_b.read_text(encoding="utf-8").strip()

        # Assert: three connections, three distinct runs.
        assert second_id not in {sibling_id, own_id}
        assert _incomplete_run_owners(tmp_path) == {sibling_id}
    finally:
        _ = gate_a.write_text("release", encoding="utf-8")
        _ = child_a.wait(timeout=60)

    # Act: a fresh process (no env id) runs init + resume.
    report = _run_fresh_resume_child(tmp_path)

    # Assert: it adopts the DEAD sibling's incomplete run — never this
    # process's live run — and continues from A's completed phase.
    assert report["session_id"] == sibling_id
    assert report["resumable"] is True
    assert report["completed_phases"] == ["select"]
    assert live_sibling_owner_ids(tmp_path) == set()


def test_empty_project_mints_per_connection(tmp_path: Path) -> None:
    """No registry, no store: every fresh connection mints its own id."""
    # Arrange
    own_id = json.loads(op_init(tmp_path, "implement", None))["session_id"]
    ready = tmp_path / "ready.json"
    child = _spawn_runner(tmp_path, ready, None)
    _ = child.wait(timeout=60)
    _wait_for_file(ready)

    # Act
    child_id = ready.read_text(encoding="utf-8").strip()

    # Assert: child never adopts the live parent's id or run.
    assert child_id != own_id
    registry = _read_registry(tmp_path)
    assert {own_id, child_id} <= set(registry)
    assert _incomplete_run_owners(tmp_path) == set()


# ---------------------------------------------------------------------------
# Adoption guard edges (simulated owner state)
# ---------------------------------------------------------------------------


def test_restart_after_owner_death_adopts_incomplete_run(tmp_path: Path) -> None:
    """A fresh process resumes the dead-owned incomplete run, not a new one."""
    # Arrange: run one phase, then simulate the owning process dying.
    run_id = json.loads(op_init(tmp_path, "implement", None))["session_id"]
    _ = op_write_result(tmp_path, "implement", "select", '{"status": "complete"}')
    registry = _read_registry(tmp_path)
    registry[run_id] = _entry([_dead_pid()])
    _write_registry(tmp_path, registry)

    # Act: fresh process (no env id) re-inits.
    _reset_pipeline_env()
    result = json.loads(op_init(tmp_path, "implement", None))

    # Assert: same run, prior phase state preserved.
    assert result["session_id"] == run_id
    assert "select" in _state_phases(tmp_path, run_id)


def test_live_sibling_run_is_never_adopted(tmp_path: Path) -> None:
    """An incomplete run owned by a live sibling is not adoptable."""
    # Arrange: incomplete run for "sib" owned by a live foreign process.
    _record_running_phase(tmp_path, "sib")
    with _live_foreign_pid() as pid:
        _write_registry(tmp_path, {"sib": _entry([pid])})

        # Act: fresh process resolves identity.
        _reset_pipeline_env()
        minted = json.loads(op_init(tmp_path, "implement", None))["session_id"]

        # Assert: a new id is minted; the sibling's run stays untouched.
        assert minted != "sib"
        assert live_sibling_owner_ids(tmp_path) == {"sib"}


def test_completed_run_is_not_adopted(tmp_path: Path) -> None:
    """Only incomplete runs are adoptable; a cleared run mints fresh."""
    # Arrange: complete and clear the run, then kill its recorded owner.
    run_id = json.loads(op_init(tmp_path, "implement", None))["session_id"]
    _ = op_write_result(tmp_path, "implement", "select", '{"status": "complete"}')
    _ = op_clear(tmp_path, "implement")
    _write_registry(
        tmp_path,
        {run_id: _entry([_dead_pid()])},
    )

    # Act
    _reset_pipeline_env()
    minted = json.loads(op_init(tmp_path, "implement", None))["session_id"]

    # Assert: the ended run's id is never resurrected.
    assert minted != run_id
    assert _incomplete_run_owners(tmp_path) == set()


def test_stale_registry_entry_is_not_adopted(tmp_path: Path) -> None:
    """A registry entry past the TTL is not adoptable, even if incomplete."""
    # Arrange: incomplete store run under a dead owner with an aged entry.
    _record_running_phase(tmp_path, "old")
    _write_registry(
        tmp_path,
        {
            "old": _entry([_dead_pid()], updated_at="2020-01-01T00:00:00+00:00"),
        },
    )

    # Act
    _reset_pipeline_env()
    minted = json.loads(op_init(tmp_path, "implement", None))["session_id"]

    # Assert
    assert minted != "old"


def test_passive_resolution_never_mutates_state(tmp_path: Path) -> None:
    """mint=False mirrors adoption without writing env or registry."""
    # Arrange: an adoptable dead-owned incomplete run exists.
    _record_running_phase(tmp_path, "gone")
    _write_registry(
        tmp_path,
        {"gone": _entry([_dead_pid()])},
    )
    before = _registry_path(tmp_path).read_text(encoding="utf-8")

    # Act
    _reset_pipeline_env()
    peeked = get_session_id(tmp_path, mint=False)

    # Assert: the adoptable id is visible, but nothing was mutated.
    assert peeked == "gone"
    assert _ENV_KEY not in os.environ
    assert _registry_path(tmp_path).read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# Resume-side disambiguation
# ---------------------------------------------------------------------------


def test_resume_never_attaches_live_sibling_run(tmp_path: Path) -> None:
    """op_resume must not fall back to a live sibling's incomplete run."""
    # Arrange: live sibling owns the only incomplete run of this pipeline.
    _record_running_phase(tmp_path, "sib")
    with _live_foreign_pid() as pid:
        _write_registry(tmp_path, {"sib": _entry([pid])})
        os.environ[_ENV_KEY] = "fresh-connection"

        # Act
        plan = cast(dict[str, object], json.loads(op_resume(tmp_path, "implement")))

    # Assert: nothing to resume — the sibling's run is invisible to us.
    assert plan["resumable"] is False
    assert "no incomplete run" in str(plan["reason"])


def test_brief_hides_live_sibling_runs(tmp_path: Path) -> None:
    """The session brief only offers runs no live sibling owns."""
    # Arrange: one dead-owned and one live-sibling-owned incomplete run.
    _record_running_phase(tmp_path, "gone")
    _record_running_phase(tmp_path, "sib")
    with _live_foreign_pid() as pid:
        _write_registry(
            tmp_path,
            {
                "gone": _entry([_dead_pid()]),
                "sib": _entry([pid]),
            },
        )

        # Act
        entries = scan_incomplete_pipeline_entries(tmp_path)

    # Assert: the resumable run is offered; the live sibling's is not.
    assert "gone/implement:select" in entries
    assert not any(entry.startswith("sib/") for entry in entries)


# ---------------------------------------------------------------------------
# Review-gap regressions: dead-run selection, explicit resume, contention,
# fail-closed claims, and pipeline-scoped identity binding
# ---------------------------------------------------------------------------


def _seed_two_dead_runs(root: Path) -> None:
    """Fresher 'newer' and older 'older' dead-owned incomplete implement runs."""
    _record_running_phase(root, "older")
    _record_running_phase(root, "newer")
    _write_registry(
        root,
        {
            "older": _entry([_dead_pid()], updated_at=_hours_ago(1)),
            "newer": _entry([_dead_pid()]),
        },
    )


def test_two_dead_owned_runs_resolve_without_sharing(tmp_path: Path) -> None:
    """Default resolution adopts the freshest; the next process gets the other."""
    # Arrange
    _seed_two_dead_runs(tmp_path)

    # Act: this fresh process resolves first.
    _reset_pipeline_env()
    first = json.loads(op_init(tmp_path, "implement", None))["session_id"]

    # Assert: freshest dead-owned run adopted.
    assert first == "newer"

    # Act: a second fresh process resolves while this one is alive.
    ready = tmp_path / "ready-second.json"
    child = _spawn_runner(tmp_path, ready, None)
    _ = child.wait(timeout=60)
    _wait_for_file(ready)
    second = ready.read_text(encoding="utf-8").strip()

    # Assert: it resumes the OTHER run — never this process's live one.
    assert second == "older"
    assert first != second


def test_explicit_resume_run_id_pins_older_run(tmp_path: Path) -> None:
    """init(resume_run_id=...) pins the requested run despite a fresher one."""
    # Arrange
    _seed_two_dead_runs(tmp_path)

    # Act: explicit resume of the OLDER run.
    _reset_pipeline_env()
    result = json.loads(op_init(tmp_path, "implement", '{"resume_run_id": "older"}'))

    # Assert: the pinned id is used and surfaced, not the fresher entry.
    assert result["session_id"] == "older"
    assert "resume_run_id" not in _state_phases(tmp_path, "older")


def test_explicit_resume_refusal_falls_back(tmp_path: Path) -> None:
    """A non-adoptable pinned id falls back to normal resolution."""
    # Arrange: a live-owned "sib" run plus two dead-owned ones.
    _seed_two_dead_runs(tmp_path)
    _record_running_phase(tmp_path, "sib")
    with _live_foreign_pid() as pid:
        registry = _read_registry(tmp_path)
        registry["sib"] = _entry([pid])
        _write_registry(tmp_path, registry)

        # Act: pin the live sibling's run.
        _reset_pipeline_env()
        result = json.loads(op_init(tmp_path, "implement", '{"resume_run_id": "sib"}'))

    # Assert: refusal -> freshest dead-owned fallback, never the sibling's.
    assert result["session_id"] == "newer"


def test_contended_adoption_single_winner(tmp_path: Path) -> None:
    """N racing fresh processes: exactly one adopts the dead run, rest mint."""
    # Arrange: one dead-owned incomplete run; four children with no barrier.
    _record_running_phase(tmp_path, "race")
    _write_registry(tmp_path, {"race": _entry([_dead_pid()])})
    spawned: list[tuple[subprocess.Popen[bytes], Path, Path]] = []
    ids: list[str] = []
    try:
        for index in range(4):
            ready = tmp_path / f"race-ready-{index}.json"
            gate = tmp_path / f"race-gate-{index}.json"
            spawned.append((_spawn_runner(tmp_path, ready, gate), ready, gate))
        for _proc, ready, _gate in spawned:
            _wait_for_file(ready)
            ids.append(ready.read_text(encoding="utf-8").strip())
    finally:
        for _proc, _ready, gate in spawned:
            _ = gate.write_text("release", encoding="utf-8")
        for proc, _ready, _gate in spawned:
            _ = proc.wait(timeout=60)

    # Assert: exactly one adopter; every other connection minted its own id.
    assert ids.count("race") == 1
    assert len(set(ids)) == 4
    registry = _read_registry(tmp_path)
    assert all(entry["owners"] for entry in registry.values())


def test_claim_lock_timeout_refuses_adoption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held claim lock makes adoption fail closed into a fresh mint."""
    # Arrange: adoptable dead-owned run; another process holds the claim lock.
    _record_running_phase(tmp_path, "locked")
    _write_registry(tmp_path, {"locked": _entry([_dead_pid()])})
    lock_file = _registry_path(tmp_path).with_suffix(".json.lock")
    _ = lock_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )
    try:
        # Act
        _reset_pipeline_env()
        minted = json.loads(op_init(tmp_path, "implement", None))["session_id"]
    finally:
        _ = lock_file.unlink(missing_ok=True)

    # Assert: fail closed — fresh id, registry untouched, no re-own.
    assert minted != "locked"
    registry = _read_registry(tmp_path)
    owners = cast(list[dict[str, object]], registry["locked"]["owners"])
    assert all(owner["pid"] != os.getpid() for owner in owners)


def test_unregistrable_inherited_env_id_switches_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An inherited id that cannot be registered is dropped before any write."""
    # Arrange: dead parent's run; this process inherits its env id.
    _record_running_phase(tmp_path, "orphan")
    _write_registry(tmp_path, {"orphan": _entry([_dead_pid()])})
    os.environ[_ENV_KEY] = "orphan"
    lock_file = _registry_path(tmp_path).with_suffix(".json.lock")
    _ = lock_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )
    try:
        # Act: first identity call under the refused lock.
        switched = get_session_id(tmp_path)
    finally:
        _ = lock_file.unlink(missing_ok=True)

    # Assert: switched to a fresh id before writing anything under the old.
    assert switched != "orphan"
    assert os.environ[_ENV_KEY] == switched
    assert not (tmp_path / ".cortex" / ".session" / "orphan" / "implement").exists()

    # Act: a later fresh claimant recovers the (writer-less) original run.
    ready = tmp_path / "ready-claimant.json"
    child = _spawn_runner(tmp_path, ready, None)
    _ = child.wait(timeout=60)
    _wait_for_file(ready)

    # Assert: never a shared live window — the child owns the only copy.
    assert ready.read_text(encoding="utf-8").strip() == "orphan"


def test_resume_binds_identity_to_reported_pipeline_run(tmp_path: Path) -> None:
    """resume(implement) never latches a fresher OTHER-pipeline run."""
    # Arrange: fresher dead quality run, older dead implement run.
    _record_running_phase(tmp_path, "irun", pipeline="implement")
    _record_running_phase(tmp_path, "qrun", pipeline="quality")
    _write_registry(
        tmp_path,
        {
            "irun": _entry([_dead_pid()], updated_at=_hours_ago(1)),
            "qrun": _entry([_dead_pid()]),
        },
    )

    # Act: fresh process resumes the implement pipeline.
    _reset_pipeline_env()
    plan = cast(dict[str, object], json.loads(op_resume(tmp_path, "implement")))

    # Assert: identity bound to the implement run's owner, not qrun.
    assert plan["session_id"] == "irun"
    assert os.environ[_ENV_KEY] == "irun"

    # Act: the process continues the resumed run.
    _ = op_write_result(tmp_path, "implement", "code", '{"status": "complete"}')

    # Assert: the write continues the ORIGINAL run window, not a new one.
    assert "code" in _state_phases(tmp_path, "irun")
    assert not (tmp_path / ".cortex" / ".session" / "qrun" / "implement").exists()


def test_resume_rebinds_when_fallback_owner_differs(tmp_path: Path) -> None:
    """A pre-latched id is switched to the run resume actually reports."""
    # Arrange: this process already minted id X (no candidates existed).
    _reset_pipeline_env()
    minted = json.loads(op_init(tmp_path, "implement", None))["session_id"]
    # A dead-owned implement run appears afterwards (crashed sibling).
    _record_running_phase(tmp_path, "late")
    _write_registry(tmp_path, {"late": _entry([_dead_pid()])})

    # Act: resume falls back to "late", then must re-bind identity to it.
    plan = cast(dict[str, object], json.loads(op_resume(tmp_path, "implement")))

    # Assert: plan, env, and future writes all use the reported owner.
    assert plan["session_id"] == "late"
    assert os.environ[_ENV_KEY] == "late"
    assert minted != "late"


def test_resume_never_reports_unregistered_legacy_run(tmp_path: Path) -> None:
    """A store run with no registry entry is never adopted or reported."""
    # Arrange: legacy incomplete store run; NO ownership-registry entry.
    _record_running_phase(tmp_path, "legacy")

    # Act: fresh process resumes the pipeline.
    _reset_pipeline_env()
    plan = cast(dict[str, object], json.loads(op_resume(tmp_path, "implement")))

    # Assert: non-resumable — never a report toward an unlatched run.
    assert plan["resumable"] is False
    latched = os.environ[_ENV_KEY]
    assert latched != "legacy"

    # Act: the process continues writing under its effective id.
    _ = op_write_result(tmp_path, "implement", "code", '{"status": "complete"}')

    # Assert: writes land under the latched id, never the legacy run.
    assert "code" in _state_phases(tmp_path, latched)
    assert not (tmp_path / ".cortex" / ".session" / "legacy" / "implement").exists()


def test_resume_bind_refusal_keeps_writes_on_effective_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Claim-lock refusal during bind never yields a resumable foreign run."""
    # Arrange: registered dead-owned incomplete run; claim lock held elsewhere.
    _record_running_phase(tmp_path, "regflict")
    _write_registry(tmp_path, {"regflict": _entry([_dead_pid()])})
    lock_file = _registry_path(tmp_path).with_suffix(".json.lock")
    _ = lock_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )
    try:
        # Act: fresh process resolves and resumes while claims are refused.
        _reset_pipeline_env()
        plan = cast(dict[str, object], json.loads(op_resume(tmp_path, "implement")))
    finally:
        _ = lock_file.unlink(missing_ok=True)

    # Assert: invariant — resumable plans always name the latched id.
    assert plan["resumable"] is False
    latched = os.environ[_ENV_KEY]
    assert latched != "regflict"

    # Act: continuation writes stay on the effective id.
    _ = op_write_result(tmp_path, "implement", "code", '{"status": "complete"}')
    assert "code" in _state_phases(tmp_path, latched)


def test_whole_op_claim_refusal_keeps_one_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Directory, manifest stamp, response, and later writes share ONE id."""
    # Arrange: the claim lock is held for the whole operation and beyond.
    lock_file = _registry_path(tmp_path).with_suffix(".json.lock")
    _ = lock_file.parent.mkdir(parents=True, exist_ok=True)
    _ = lock_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )
    try:
        # Act: init under continued refusal.
        result = json.loads(op_init(tmp_path, "implement", None))

        # Assert: one identity across directory, manifest, and response.
        directory = Path(str(result["pipeline_dir"]))
        assert result["session_id"] == directory.parent.name
        manifest = json.loads((directory / "pipeline.json").read_text(encoding="utf-8"))
        assert manifest["session_id"] == result["session_id"]

        # Act: a subsequent write under continued refusal stays in place.
        _ = op_write_result(tmp_path, "implement", "code", '{"status": "complete"}')
        assert (directory / "code-result.json").exists()
    finally:
        _ = lock_file.unlink(missing_ok=True)

    # Assert: exactly one run directory exists — no stray re-mints.
    session_root = tmp_path / ".cortex" / ".session"
    run_dirs = [p.name for p in session_root.iterdir() if p.is_dir()]
    assert run_dirs == [result["session_id"]]


def test_concurrent_cold_resolutions_yield_one_id(tmp_path: Path) -> None:
    """A barrier-released thread race mints exactly one identity."""
    # Arrange: eight threads race their first resolution on a fresh project.
    _reset_pipeline_env()
    barrier = threading.Barrier(8)
    results: list[str] = []
    results_lock = threading.Lock()

    def resolve() -> None:
        _ = barrier.wait(timeout=30)
        resolved = get_session_id(tmp_path)
        with results_lock:
            results.append(resolved)

    threads = [threading.Thread(target=resolve) for _ in range(8)]
    for thread in threads:
        _ = thread.start()
    for thread in threads:
        _ = thread.join(timeout=30)

    # Act is the race itself; assert the transaction serialized them all.
    assert len(results) == 8
    assert set(results) == {results[0]}
    assert os.environ[_ENV_KEY] == results[0]
    registry = _read_registry(tmp_path)
    assert set(registry) == {results[0]}
    owners = cast(list[dict[str, object]], registry[results[0]]["owners"])
    assert owners == [{"pid": os.getpid(), "host": platform.node()}]


def test_refused_bind_never_requeries_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused bind answers non-resumable with NO second store query.

    Regression (TOCTOU): the old refused-bind path re-queried the store to
    rebuild the plan, so a run created between the reads could be reported
    resumable while the identity latch stayed put.
    """
    # Arrange: a legacy store run with no registry entry; plan builds counted.
    _record_running_phase(tmp_path, "legacy")
    from unittest.mock import Mock

    from cortex.experience.resume import build_resume_plan

    spy = Mock(side_effect=build_resume_plan)
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_resume.build_resume_plan", spy
    )

    # Act: fresh process resumes; the bind on "legacy" must be refused.
    _reset_pipeline_env()
    plan = cast(dict[str, object], json.loads(op_resume(tmp_path, "implement")))

    # Assert: exact non-resumable after exactly ONE store query.
    assert plan["resumable"] is False
    assert spy.call_count == 1
    assert os.environ[_ENV_KEY] != "legacy"


def test_live_activity_refreshes_aged_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A long-idle connection's fresh run stays resumable after its death."""
    # Arrange: connection X registered, then its entry looks ancient.
    monkeypatch.setenv(_ENV_KEY, "X")
    _ = op_init(tmp_path, "implement", None)
    aged = _read_registry(tmp_path)
    aged["X"]["updated_at"] = _hours_ago(5)
    _write_registry(tmp_path, aged)

    # Act: the still-alive connection starts a fresh run (refreshing the
    # stamp through live activity), then dies with its ownership record.
    _ = op_write_result(tmp_path, "implement", "select", '{"status": "complete"}')
    refreshed = _read_registry(tmp_path)
    refreshed["X"]["owners"] = [{"pid": _dead_pid(), "host": platform.node()}]
    _write_registry(tmp_path, refreshed)

    # Assert: a restarting process adopts the fresh run despite the aged
    # start — live activity kept the entry fresh.
    _reset_pipeline_env()
    adopted = json.loads(op_init(tmp_path, "implement", None))["session_id"]
    assert adopted == "X"
    assert "select" in _state_phases(tmp_path, "X")


def _scan_empty_on_first_call(
    real_scan: Callable[..., object], calls: list[int]
) -> Callable[..., object]:
    """Wrap scan_incomplete_runs so exactly the first call sees no runs."""

    def scan(
        project_root: Path,
        ttl_seconds: float | None = None,
        now: datetime | None = None,
    ) -> object:
        calls.append(1)
        if len(calls) == 1:
            return []
        return real_scan(project_root, ttl_seconds, now)

    return scan


def _plan_closing_target_before_second_call(
    real_plan: Callable[..., object], calls: list[int], target_run: str
) -> Callable[..., object]:
    """Wrap build_resume_plan so the second call closes target_run's window."""

    def plan(
        project_root: Path,
        session_id: str,
        pipeline: str,
        *,
        excluded_owners: frozenset[str] | None = None,
    ) -> object:
        calls.append(1)
        if len(calls) == 2:
            from cortex.experience.recorder import record_run_end

            _ = record_run_end(
                project_root, target_run, pipeline, "cleared", enabled=True
            )
        if excluded_owners is None:
            return real_plan(project_root, session_id, pipeline)
        return real_plan(
            project_root, session_id, pipeline, excluded_owners=excluded_owners
        )

    return plan


def test_successful_bind_losing_its_run_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bind that immediately loses its run reports non-resumable.

    Regression: the successful-bind rebuild could fall back to another
    dead run when the just-claimed run's window closed between the claim
    and the rebuild query — resumable C reported while the latch holds B.
    """
    # Arrange: older dead run C, fresher dead-owned registered run B; the
    # selection query sees nothing (fresh mint), the plan queries see all.
    _record_running_phase(tmp_path, "C")
    # AI: store activity ties at second precision and the fallback sort is
    # stable, so B must be strictly fresher than C to be targeted first.
    time.sleep(1.1)
    _record_running_phase(tmp_path, "B")
    _write_registry(tmp_path, {"B": _entry([_dead_pid()])})
    from cortex.experience.resume import build_resume_plan, scan_incomplete_runs

    monkeypatch.setattr(
        "cortex.experience.resume.scan_incomplete_runs",
        _scan_empty_on_first_call(scan_incomplete_runs, []),
    )
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_resume.build_resume_plan",
        _plan_closing_target_before_second_call(build_resume_plan, [], "B"),
    )

    # Act: fresh process resumes; the bind on B succeeds, then B's window
    # closes right before the rebuild query.
    _reset_pipeline_env()
    plan = cast(dict[str, object], json.loads(op_resume(tmp_path, "implement")))

    # Assert: never a fallback to C — non-resumable, latch stays B, and
    # the continuation write lands under B.
    assert plan["resumable"] is False
    assert "no longer available" in str(plan["reason"])
    assert os.environ[_ENV_KEY] == "B"
    _ = op_write_result(tmp_path, "implement", "code", '{"status": "complete"}')
    assert "code" in _state_phases(tmp_path, "B")
