"""Unit tests for identity-resolution edge paths (coverage of new code).

Companion to ``test_pipeline_handoff_concurrent_runs.py`` (integration):
these tests pin the defensive branches of the run-ownership registry —
malformed files, unparseable timestamps, liveness-signal failures, and
lock cleanup errors — so degradation is always silent-by-design. Behavior
is exercised through the public surface; helpers here are module-local.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import pytest

from cortex.tools.session.pipeline_handoff_io import op_init
from cortex.tools.session.pipeline_handoff_lock import (
    PipelineClaimLockTimeout,
    pipeline_claim_lock,
    pipeline_state_lock,
)
from cortex.tools.session.pipeline_handoff_session import (
    bind_session_id,
    get_session_id,
    live_sibling_owner_ids,
)

_ENV_KEY = "CORTEX_PIPELINE_SESSION_ID"
_REGISTRY_RELATIVE = ".cortex/.session/.pipeline-runs.json"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fresh-process env on both ends; experience recording at default."""
    saved = os.environ.get(_ENV_KEY)
    _ = os.environ.pop(_ENV_KEY, None)
    monkeypatch.delenv("CORTEX_EXPERIENCE_RECORDING", raising=False)
    yield
    if saved is None:
        _ = os.environ.pop(_ENV_KEY, None)
    else:
        os.environ[_ENV_KEY] = saved


def _registry_path(root: Path) -> Path:
    return root / _REGISTRY_RELATIVE


def _write_registry_payload(root: Path, payload: dict[str, object]) -> None:
    path = _registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _dead_pid() -> int:
    """A pid that certainly belonged to a process that has exited."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    _ = proc.wait(timeout=30)
    return proc.pid


def _entry(owner_pids: list[int], *, updated_at: str = "") -> dict[str, object]:
    stamp = updated_at or time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    return {
        "owners": [{"pid": pid, "host": platform.node()} for pid in owner_pids],
        "updated_at": stamp,
    }


@contextmanager
def _live_foreign_pid() -> Iterator[int]:
    proc = subprocess.Popen(["sleep", "60"])
    try:
        yield proc.pid
    finally:
        proc.terminate()
        _ = proc.wait(timeout=30)


def _raise_oserror(*_args: object, **_kwargs: object) -> None:
    raise OSError("patched failure")


def _raise_oserror_only_for(target: Path) -> Callable[..., os.stat_result]:
    """Path.stat replacement failing only for ``target`` (others delegate)."""
    original = Path.stat

    def stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if self == target:
            raise OSError("patched failure")
        return original(self, follow_symlinks=follow_symlinks)

    return stat


def _held_claim_lock(root: Path) -> Path:
    """Create and return a held registry claim-lock file."""
    lock_file = _registry_path(root).with_suffix(".json.lock")
    _ = lock_file.parent.mkdir(parents=True, exist_ok=True)
    _ = lock_file.write_text("", encoding="utf-8")
    return lock_file


# ---------------------------------------------------------------------------
# Owner liveness signals (os.kill success / error -> conservatively alive)
# ---------------------------------------------------------------------------


def test_live_same_host_owner_is_reported_alive(tmp_path: Path) -> None:
    """A live same-host pid keeps its run out of live-sibling hiding."""
    # Arrange: registry entry owned by a live foreign same-host process.
    with _live_foreign_pid() as pid:
        _write_registry_payload(tmp_path, {"live": _entry([pid])})

        # Act
        live_ids = live_sibling_owner_ids(tmp_path)

    # Assert: os.kill succeeded on the live pid -> owner counted alive.
    assert live_ids == {"live"}


def test_foreign_host_owner_counts_as_alive(tmp_path: Path) -> None:
    """An owner on another host is conservatively alive (unknowable)."""
    # Arrange: dead pid recorded on a foreign host.
    _write_registry_payload(
        tmp_path,
        {"far": {"owners": [{"pid": _dead_pid(), "host": "other-host"}]}},
    )

    # Act
    live_ids = live_sibling_owner_ids(tmp_path)

    # Assert: never treated as adoptable dead.
    assert live_ids == {"far"}


def test_kill_error_counts_owner_as_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Permission-style kill errors mean the pid exists: conservative alive."""

    def deny(_pid: int, _sig: int) -> None:
        raise PermissionError("not ours")

    # Arrange
    monkeypatch.setattr(os, "kill", deny)
    _write_registry_payload(tmp_path, {"locked": _entry([_dead_pid()])})

    # Act
    live_ids = live_sibling_owner_ids(tmp_path)

    # Assert: undecidable signal degrades to alive, never to adoption risk.
    assert live_ids == {"locked"}


# ---------------------------------------------------------------------------
# Registry parsing and pruning edge cases
# ---------------------------------------------------------------------------


def test_malformed_registry_payloads_parse_to_nothing(tmp_path: Path) -> None:
    """Bad JSON, non-dict payloads, and invalid entries are all skipped."""
    # Arrange: three malformed variants.
    marker = _registry_path(tmp_path)
    _ = marker.parent.mkdir(parents=True, exist_ok=True)
    for payload in ('"not-a-dict"', "[1, 2]", "{bad json", '{"": {}}'):
        _ = marker.write_text(payload, encoding="utf-8")

        # Act / Assert: parsing degrades to an empty registry
        # (an empty-string run id is skipped like any malformed entry).
        assert live_sibling_owner_ids(tmp_path) == set()


def test_invalid_registry_entry_is_skipped(tmp_path: Path) -> None:
    """A well-formed JSON dict that fails entry validation is skipped."""
    # Arrange: owners must be a list; a string fails _RunEntry validation.
    _write_registry_payload(
        tmp_path, {"broken": {"owners": "nope", "updated_at": "2026-01-01"}}
    )

    # Act
    live_ids = live_sibling_owner_ids(tmp_path)

    # Assert
    assert live_ids == set()


def test_prune_keeps_entries_with_unparseable_timestamps(tmp_path: Path) -> None:
    """An unparseable updated_at is treated as not-expired (conservative)."""
    # Arrange: dead-owned entry whose timestamp cannot be parsed.
    _write_registry_payload(
        tmp_path,
        {
            "g": {
                "owners": [{"pid": _dead_pid(), "host": platform.node()}],
                "updated_at": "x",
            }
        },
    )

    # Act: any registering resolution prunes the registry under the lock.
    _ = get_session_id(tmp_path)

    # Assert: the garbage-timestamp entry survived the prune.
    kept = cast(dict[str, object], json.loads(_registry_path(tmp_path).read_text()))
    assert "g" in kept


# ---------------------------------------------------------------------------
# Selection edges (sort key + freshness on unparseable timestamps)
# ---------------------------------------------------------------------------


def _seed_two_run_ids(tmp_path: Path) -> None:
    """One adoptable run plus a garbage-timestamp dead-owned entry."""
    from cortex.experience.recorder import record_phase_event

    _ = record_phase_event(
        tmp_path, "good", "implement", "select", "running", enabled=True
    )
    _write_registry_payload(
        tmp_path,
        {
            "good": _entry([_dead_pid()]),
            "bad": {
                "owners": [{"pid": _dead_pid(), "host": platform.node()}],
                "updated_at": "?",
            },
        },
    )


def test_selection_skips_unparseable_timestamp_entries(tmp_path: Path) -> None:
    """Garbage timestamps sort last and are never adoptable."""
    # Arrange
    _seed_two_run_ids(tmp_path)

    # Act
    resolved = json.loads(op_init(tmp_path, "implement", None))["session_id"]

    # Assert: the valid entry wins; the garbage one is not fresh.
    assert resolved == "good"


# ---------------------------------------------------------------------------
# Registration degradation
# ---------------------------------------------------------------------------


def test_registration_oserror_degrades_to_warning(tmp_path: Path) -> None:
    """An unwritable registry degrades to an unregistered mint, never raises."""
    # Arrange: .cortex/.session exists as a FILE, so registry writes fail.
    session_dir = tmp_path / ".cortex" / ".session"
    _ = session_dir.parent.mkdir(parents=True, exist_ok=True)
    _ = session_dir.write_text("", encoding="utf-8")

    # Act
    minted = get_session_id(tmp_path)

    # Assert: an id is still resolved (unregistered; others cannot adopt it).
    assert minted


def test_unregistrable_inherited_id_switches_when_claims_time_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both claim attempts timing out makes the inherited id switch."""
    # Arrange: env id with no registry entry, claim lock held throughout.
    os.environ[_ENV_KEY] = "ghost"
    lock_file = _held_claim_lock(tmp_path)
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )
    try:
        # Act
        resolved = get_session_id(tmp_path)

        # Assert: registration reported failure -> fresh id minted.
        assert resolved != "ghost"
        assert os.environ[_ENV_KEY] == resolved
    finally:
        _ = lock_file.unlink(missing_ok=True)


def test_env_id_kept_when_already_recorded_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused re-registration still keeps an id we already own on record."""
    # Arrange: this process is a recorded owner, but the lock is held.
    _write_registry_payload(tmp_path, {"mine": _entry([os.getpid()])})
    os.environ[_ENV_KEY] = "mine"
    lock_file = _held_claim_lock(tmp_path)
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )
    try:
        # Act
        resolved = get_session_id(tmp_path)

        # Assert: durable ownership needs no further write.
        assert resolved == "mine"
    finally:
        _ = lock_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Binding and passive resolution edges
# ---------------------------------------------------------------------------


def test_bind_is_noop_when_already_bound(tmp_path: Path) -> None:
    """Binding the id the process already holds changes nothing."""
    # Arrange
    os.environ[_ENV_KEY] = "held"
    _write_registry_payload(tmp_path, {"held": _entry([os.getpid()])})
    before = _registry_path(tmp_path).read_text(encoding="utf-8")

    # Act
    bound = bind_session_id(tmp_path, "held")

    # Assert
    assert bound == "held"
    assert _registry_path(tmp_path).read_text(encoding="utf-8") == before


def test_passive_resolution_on_empty_project_returns_empty(tmp_path: Path) -> None:
    """mint=False with no env id and no candidates resolves to empty."""
    # Arrange: fresh project, no registry, no store.

    # Act
    peeked = get_session_id(tmp_path, mint=False)

    # Assert
    assert peeked == ""
    assert _ENV_KEY not in os.environ


# ---------------------------------------------------------------------------
# Lock cleanup robustness
# ---------------------------------------------------------------------------


def test_stale_lock_stat_error_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: held lock; stat fails only for that lock file during polling.
    lock_file = _held_claim_lock(tmp_path)
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(Path, "stat", _raise_oserror_only_for(lock_file))
        # Act / Assert: the claim times out cleanly instead of raising OSError.
        with pytest.raises(PipelineClaimLockTimeout):
            with pipeline_claim_lock(_registry_path(tmp_path)):
                pass
    _ = lock_file.unlink(missing_ok=True)


def test_stale_lock_unlink_error_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale lock that cannot be unlinked still ends in a clean timeout."""
    # Arrange: ancient lock mtime; unlink fails only during the attempt.
    lock_file = _held_claim_lock(tmp_path)
    past = time.time() - 10_000
    os.utime(lock_file, (past, past))
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_lock._CLAIM_LOCK_TIMEOUT_SECONDS", 0.2
    )

    # Act / Assert: stale clear + failing unlink still end in a timeout.
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(Path, "unlink", _raise_oserror)
        with pytest.raises(PipelineClaimLockTimeout):
            with pipeline_claim_lock(_registry_path(tmp_path)):
                pass


def test_claim_lock_swallows_unlink_error_on_release(tmp_path: Path) -> None:
    """Releasing a claim lock whose unlink fails never raises to the claimer."""
    # Arrange
    target = tmp_path / "claim-target.json"
    with pytest.MonkeyPatch.context() as patcher:
        with pipeline_claim_lock(target):
            patcher.setattr(Path, "unlink", _raise_oserror)
        # Act is the context exit with a failing unlink.

    # Assert: exit completed without raising; clean up for tmp_path teardown.
    target.with_suffix(".json.lock").unlink(missing_ok=True)


def test_state_lock_swallows_unlink_error_on_release(tmp_path: Path) -> None:
    """Same guarantee for the best-effort state lock."""
    # Arrange
    target = tmp_path / "state-target.json"
    with pytest.MonkeyPatch.context() as patcher:
        with pipeline_state_lock(target):
            patcher.setattr(Path, "unlink", _raise_oserror)
        # Act is the context exit with a failing unlink.

    # Assert
    target.with_suffix(".json.lock").unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# init data coercion (io)
# ---------------------------------------------------------------------------


def test_init_wraps_non_dict_data_as_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-dict JSON and invalid JSON init payloads land in state["raw"]."""
    # Arrange
    monkeypatch.setenv(_ENV_KEY, "rawwrap")
    manifest_path = (
        tmp_path / ".cortex" / ".session" / "rawwrap" / "implement" / "pipeline.json"
    )

    # Act: valid JSON that is not an object keeps its raw text.
    _ = json.loads(op_init(tmp_path, "implement", '"plain text"'))
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text()))
    assert manifest["raw"] == '"plain text"'

    # Act: not JSON at all.
    _ = json.loads(op_init(tmp_path, "implement", "not json{"))
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text()))

    # Assert
    assert manifest["raw"] == "not json{"
