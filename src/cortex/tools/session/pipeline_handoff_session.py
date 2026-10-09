"""Run-id resolution for pipeline_handoff — one pipeline run per connection.

Each MCP server process (one orchestrator connection) owns its own pipeline
run id, so concurrent siblings never share a run window: phase files live
under ``.cortex/.session/{run_id}/{pipeline}/`` and the store opens one
lineage per id — interleaved phase events are impossible.

Restart-resume is explicit: a fresh process mints a NEW run id unless it
can adopt one via the run-ownership registry
(``.cortex/.session/.pipeline-runs.json``), mapping each run id to its
owning processes. Adoptable = TTL-fresh entry, no live *other* owner, and
the store lists an incomplete run scoped to the pipeline being resolved
(``init``'s ``resume_run_id`` payload key pins a candidate under the same
guards). Claims re-own under a fail-closed lock — on contention a fresh
process mints instead, and an inherited id that cannot be registered is
switched for a fresh one, so no two processes ever write one run window.
Subagents inherit ``CORTEX_PIPELINE_SESSION_ID`` and register as
*additional* owners, keeping a run un-adoptable while any participant
lives. The registry is a resume *hint*, never live identity; the legacy
ownerless marker (``.active-session.json``) is intentionally ignored.

Identity domains (do not merge them again):

- ``CORTEX_PIPELINE_SESSION_ID`` — this module's per-connection pipeline
  run identity, latched into its own env var and inherited by subagents.
- ``CORTEX_SESSION_ID`` — per-process agent identity owned by
  ``cortex.core.session_logger`` (session registry, task locks, WAL).

These were previously the same env var; the fusion made every concurrent
MCP server process one agent id, hiding siblings from each other.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field, ValidationError

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

from .pipeline_handoff_clock import age_seconds, parse_iso
from .pipeline_handoff_clock import now_iso as _now_iso
from .pipeline_handoff_lock import PipelineClaimLockTimeout, pipeline_claim_lock

logger = logging.getLogger(__name__)

_PIPELINE_SESSION_ENV_KEY = "CORTEX_PIPELINE_SESSION_ID"
_RUNS_REGISTRY_FILENAME = ".pipeline-runs.json"

# Mirrors pipeline_handoff_io.PIPELINE_TTL_SECONDS: a registry entry older
# than this is treated as abandoned rather than resumed.
SESSION_MARKER_TTL_SECONDS = 4 * 3600  # 4 hours

_HOST = platform.node()

# AI: two-level locking — this thread lock serializes the whole identity
# transaction (env read > select > mint/adopt > latch) inside one process
# (overlapping asyncio.to_thread workers would otherwise mint two ids and
# overwrite the shared latch); the file claim lock inside serializes
# cross-process registry claims. Order: thread lock -> claim lock, only.
_RESOLUTION_LOCK = threading.Lock()
# AI: self-mint provenance keyed by pid, so a forked child inheriting the
# set never treats a parent mint as its own (inherited-id rules apply).
_SELF_MINTED_RUN_IDS: set[tuple[int, str]] = set()


class _RunOwner(BaseModel):
    """One process recorded as an owner of a pipeline run id."""

    pid: int
    host: str


class _RunEntry(BaseModel):
    """Registry record for one pipeline run id."""

    owners: list[_RunOwner] = Field(default_factory=list[_RunOwner])
    updated_at: str = ""


def _runs_registry_path(project_root: Path) -> Path:
    base = get_cortex_path(project_root, CortexResourceType.SESSION)
    return base / _RUNS_REGISTRY_FILENAME


def _current_owner() -> _RunOwner:
    return _RunOwner(pid=os.getpid(), host=_HOST)


def _owner_alive(owner: _RunOwner) -> bool:
    """True when the owner process is provably alive.

    # AI: undecidable signals (foreign host, permission error) count as
    # alive — adopting a live sibling's run is the bug this module prevents.
    """
    if owner.host != _HOST:
        return True
    try:
        os.kill(owner.pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _has_live_foreign_owner(entry: _RunEntry) -> bool:
    me = _current_owner()
    return any(_owner_alive(owner) and owner != me for owner in entry.owners)


def _load_run_registry(project_root: Path) -> dict[str, _RunEntry]:
    """Parse the ownership registry; malformed entries are skipped."""
    registry: dict[str, _RunEntry] = {}
    try:
        raw: object = json.loads(
            _runs_registry_path(project_root).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return registry
    if not isinstance(raw, dict):
        return registry
    for run_id, value in cast(dict[str, object], raw).items():
        if not run_id:
            continue
        try:
            registry[run_id] = _RunEntry.model_validate(value)
        except ValidationError:
            continue
    return registry


def _save_run_registry(project_root: Path, registry: dict[str, _RunEntry]) -> None:
    """Atomically persist the registry; caller must hold the claim lock."""
    path = _runs_registry_path(project_root)
    payload = {run_id: entry.model_dump() for run_id, entry in registry.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(f"{path.suffix}.tmp")
    _ = temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _ = temp_file.replace(path)


def _prune_stale_entries(
    registry: dict[str, _RunEntry],
) -> dict[str, _RunEntry]:
    """Drop dead-owned entries past the TTL.

    # AI: entries with any live owner never expire — an idle-but-alive
    # connection's run must not become adoptable by registry aging.
    """
    kept: dict[str, _RunEntry] = {}
    for run_id, entry in registry.items():
        try:
            expired = age_seconds(entry.updated_at) > SESSION_MARKER_TTL_SECONDS
        except (ValueError, TypeError):
            expired = False
        if expired and not any(_owner_alive(o) for o in entry.owners):
            continue
        kept[run_id] = entry
    return kept


def _store_incomplete_owner_ids(
    project_root: Path, pipeline: str | None
) -> frozenset[str]:
    """Run ids with an open store window, optionally scoped to one pipeline.

    # AI: lazy import keeps this importable without the experience package.
    """
    from cortex.experience.resume import scan_incomplete_runs

    return frozenset(
        run.owner
        for run in scan_incomplete_runs(project_root)
        if run.owner and (pipeline is None or run.pipeline == pipeline)
    )


def _entry_sort_key(item: tuple[str, _RunEntry]) -> datetime:
    try:
        return parse_iso(item[1].updated_at)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _entry_adoptable(
    project_root: Path, run_id: str, entry: _RunEntry, pipeline: str | None
) -> bool:
    """True when this process may adopt ``run_id`` (read-only check).

    Guards: no live foreign owner; self-owned always adoptable; others
    TTL-fresh with an incomplete ``pipeline``-scoped store run.
    """
    if _has_live_foreign_owner(entry):
        return False
    if _current_owner() in entry.owners:
        return True
    try:
        fresh = age_seconds(entry.updated_at) <= SESSION_MARKER_TTL_SECONDS
    except (ValueError, TypeError):
        fresh = False
    return fresh and run_id in _store_incomplete_owner_ids(project_root, pipeline)


def _select_adoptable_run_id(project_root: Path, pipeline: str | None) -> str | None:
    """Freshest adoptable run id, or None (read-only; see _entry_adoptable)."""
    for run_id, entry in sorted(
        _load_run_registry(project_root).items(), key=_entry_sort_key, reverse=True
    ):
        if _entry_adoptable(project_root, run_id, entry, pipeline):
            return run_id
    return None


def _preferred_or_adoptable(
    project_root: Path, prefer_run_id: str | None, pipeline: str | None
) -> str | None:
    """Explicit resume candidate when adoptable, else the freshest candidate."""
    if prefer_run_id is not None:
        entry = _load_run_registry(project_root).get(prefer_run_id)
        if entry is not None and _entry_adoptable(
            project_root, prefer_run_id, entry, pipeline
        ):
            return prefer_run_id
    return _select_adoptable_run_id(project_root, pipeline)


def _register_owned_id(project_root: Path, session_id: str) -> bool:
    """Record this process as an owner; True when ownership is durable."""
    me = _current_owner()
    for _attempt in (0, 1):
        try:
            with pipeline_claim_lock(_runs_registry_path(project_root)):
                registry = _prune_stale_entries(_load_run_registry(project_root))
                entry = registry.setdefault(session_id, _RunEntry())
                if me not in entry.owners:
                    entry.owners.append(me)
                # AI: refresh updated_at on live activity — a long-lived
                # connection must not age past the TTL while driving runs,
                # or a post-crash restart rejects its freshest run stale.
                entry.updated_at = _now_iso()
                _save_run_registry(project_root, registry)
                return True
        except PipelineClaimLockTimeout:
            continue
        except OSError:
            logger.warning(
                "pipeline_handoff: failed to persist run registry at %s",
                _runs_registry_path(project_root),
            )
            return False
    logger.warning("pipeline_handoff: claim lock refused for run id %s", session_id)
    return False


def _id_has_current_owner(project_root: Path, session_id: str) -> bool:
    entry = _load_run_registry(project_root).get(session_id)
    return entry is not None and _current_owner() in entry.owners


def _use_registered_env_id(project_root: Path, session_id: str) -> str:
    """Ensure the env id is durably owned before this process writes under it.

    # AI: an inherited id must not run unregistered (a later claimant
    # could adopt the live run); keep it when registered, already a
    # recorded owner, or self-minted — else mint fresh and re-latch.
    """
    if _register_owned_id(project_root, session_id):
        return session_id
    if _id_has_current_owner(project_root, session_id):
        return session_id
    if (os.getpid(), session_id) in _SELF_MINTED_RUN_IDS:
        return session_id
    fresh = _mint_run_id(project_root)
    os.environ[_PIPELINE_SESSION_ENV_KEY] = fresh
    logger.warning(
        "pipeline_handoff: registration refused for '%s'; switched to fresh run id '%s'",
        session_id,
        fresh,
    )
    return fresh


def _mint_run_id(project_root: Path) -> str:
    session_id = uuid.uuid4().hex[:12]
    # AI: provenance is recorded even when registration fails — a
    # self-minted unregistered id is unadoptable by others, so repeated
    # resolutions under continued refusal return the SAME id.
    _SELF_MINTED_RUN_IDS.add((os.getpid(), session_id))
    _ = _register_owned_id(project_root, session_id)
    return session_id


def _claim_run_id(project_root: Path, candidate: str) -> str | None:
    """Claim ``candidate`` under the strict registry lock, or None.

    # AI: re-checked inside the claim lock; timeout fails CLOSED — unlocked,
    # two fresh processes could adopt the same dead-owned run.
    """
    me = _current_owner()
    try:
        with pipeline_claim_lock(_runs_registry_path(project_root)):
            registry = _prune_stale_entries(_load_run_registry(project_root))
            entry = registry.get(candidate)
            if entry is None or _has_live_foreign_owner(entry):
                return None
            if me not in entry.owners:
                entry.owners.append(me)
            entry.updated_at = _now_iso()
            _save_run_registry(project_root, registry)
            return candidate
    except (PipelineClaimLockTimeout, OSError) as exc:
        logger.warning("pipeline_handoff: run claim failed for %s: %s", candidate, exc)
        return None


def _adopt_run_id(project_root: Path, candidate: str) -> str:
    """Take ownership of ``candidate``; mint fresh when the claim refuses."""
    claimed = _claim_run_id(project_root, candidate)
    if claimed is not None:
        return claimed
    return _mint_run_id(project_root)


def bind_session_id(project_root: Path, run_id: str) -> str:
    """Bind this process's pipeline identity to ``run_id`` when allowed.

    # AI: resume may report a run whose owner differs from our resolved id;
    # binding keeps plan and writes on the id in effect after the claim.
    """
    with _RESOLUTION_LOCK:
        current = os.environ.get(_PIPELINE_SESSION_ENV_KEY, "")
        if current == run_id:
            return current
        claimed = _claim_run_id(project_root, run_id)
        if claimed is None:
            return current
        os.environ[_PIPELINE_SESSION_ENV_KEY] = claimed
        return claimed


def live_sibling_owner_ids(project_root: Path) -> frozenset[str]:
    """Run ids owned by OTHER live processes; never safe to attach.

    Consumers hide runs a live sibling still owns; ids owned only by the
    current process are excluded — a process must always see its own run.
    """
    registry = _load_run_registry(project_root)
    return frozenset(
        run_id for run_id, entry in registry.items() if _has_live_foreign_owner(entry)
    )


def get_session_id(
    project_root: Path,
    *,
    mint: bool = True,
    prefer_run_id: str | None = None,
    pipeline: str | None = None,
) -> str:
    """Get or create this connection's pipeline run id for the project.

    Resolution: latched ``CORTEX_PIPELINE_SESSION_ID`` (an inherited,
    unregistrable id is switched for a fresh one; a self-minted one is
    kept) > adoption of a dead-owned incomplete registry run scoped to
    ``pipeline`` (``prefer_run_id`` pins a candidate under the same
    guards) > fresh mint. Claims fail closed. ``mint=False`` resolves
    read-only ("" when nothing is resumable) for passive checks.
    """
    with _RESOLUTION_LOCK:
        return _resolve_session_id(project_root, mint, prefer_run_id, pipeline)


def _resolve_session_id(
    project_root: Path, mint: bool, prefer_run_id: str | None, pipeline: str | None
) -> str:
    session_id = os.environ.get(_PIPELINE_SESSION_ENV_KEY)
    if session_id:
        if mint:
            session_id = _use_registered_env_id(project_root, session_id)
        return session_id
    candidate = _preferred_or_adoptable(project_root, prefer_run_id, pipeline)
    if candidate is not None:
        if mint:
            candidate = _adopt_run_id(project_root, candidate)
            os.environ[_PIPELINE_SESSION_ENV_KEY] = candidate
        return candidate
    if not mint:
        return ""
    session_id = _mint_run_id(project_root)
    os.environ[_PIPELINE_SESSION_ENV_KEY] = session_id
    return session_id
