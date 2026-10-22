"""Selected-input validation for the existing optimization resource cache."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from cortex.core.cache import TTLCache
from cortex.tools.context.layers import ContextLayer, LayerResult
from cortex.tools.context.recent_artifacts_context import (
    build_recent_artifacts_markdown,
)
from cortex.tools.context.scoped_context import resolve_plan_scope
from cortex.tools.context.scoped_plan_evidence import (
    capture_plan_evidence,
    plan_membership_unchanged,
)
from cortex.tools.context.scoped_snapshot import ScopedSnapshot
from cortex.tools.context.scoped_state_evidence import (
    capture_goal_evidence,
    capture_rule_evidence,
    capture_task_summaries,
)
from cortex.tools.optimization.context_appenders import (
    read_explore_summary_markdown,
    read_recent_ingested_sources_markdown,
    read_recent_operations_lines,
)


def _capture_summaries(snapshot: ScopedSnapshot, config: dict[str, object]) -> None:
    root = snapshot.root
    snapshot.summaries = {
        "recent_operations": read_recent_operations_lines(root, snapshot.read),
        "recent_artifacts": build_recent_artifacts_markdown(root, snapshot.read),
        "recent_ingested_sources": read_recent_ingested_sources_markdown(
            root, snapshot.read
        ),
        "explore_summary": read_explore_summary_markdown(root, snapshot.read, config),
    }
    for name, summary in snapshot.summaries.items():
        snapshot.add_text(
            f"summary:{name}", json.dumps(summary), "context-summary", name
        )


async def prepare_scoped_snapshot(
    root: Path, config: dict[str, object]
) -> ScopedSnapshot | None:
    """Re-select only existing scoped inputs, never source paths mentioned in plans."""
    scope = resolve_plan_scope(config)
    if (
        scope is None
        or not scope.startswith("plan:")
        or not scope.removeprefix("plan:").strip()
    ):
        return None
    from cortex.tools.optimization import handlers

    snapshot = ScopedSnapshot(
        root=root.resolve(), scope=f"plan:{scope.split(':', 1)[1].strip()}"
    )
    capture_plan_evidence(snapshot)
    capture_goal_evidence(snapshot)
    capture_rule_evidence(snapshot, await handlers.get_relevant_rules())
    _capture_summaries(snapshot, config)
    selected_config = {
        key: config.get(key) for key in ("scope", "plan_file", "explore_log_path")
    }
    snapshot.add_text(
        "scope-config",
        json.dumps(selected_config, sort_keys=True),
        "configuration",
        "session scope selection",
    )
    capture_task_summaries(snapshot, config)
    return snapshot


def _coherent(snapshot: ScopedSnapshot | None) -> bool:
    return snapshot is None or (
        snapshot.files_unchanged() and plan_membership_unchanged(snapshot)
    )


def _incoherent_response(snapshot: ScopedSnapshot | None) -> str:
    return json.dumps(
        {
            "status": "error",
            "error": "incoherent_scoped_snapshot",
            "message": "Selected inputs changed during context assembly; retry a fresh read. No mixed response was cached.",
            "sources": sorted(snapshot.sources) if snapshot else [],
        },
        indent=2,
        sort_keys=True,
    )


async def load_revision_bound_context(
    root: Path,
    config: dict[str, object],
    cache_key: str,
    cache: TTLCache[tuple[str, str]],
    assemble: Callable[[ScopedSnapshot | None], Awaitable[str]],
) -> str:
    """Keep one TTL entry per request key; fingerprints validate, not multiply keys."""
    cache_key = f"{root.resolve()}:{cache_key}"
    snapshot = await prepare_scoped_snapshot(root, config)
    fingerprint = snapshot.fingerprint() if snapshot else ""
    if not _coherent(snapshot):
        return _incoherent_response(snapshot)
    # BELIEF: This TTL entry belongs to the resolved root and carries its selected-input fingerprint.
    cached = cache.get(cache_key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]
    out = await assemble(snapshot)
    if snapshot is not None:
        fresh = await prepare_scoped_snapshot(root, config)
        if (
            not _coherent(snapshot)
            or not _coherent(fresh)
            or fresh is None
            or fresh.fingerprint() != fingerprint
        ):
            return _incoherent_response(snapshot)
    cache.set(cache_key, (fingerprint, out))
    return out


def parse_context_layers(raw_layers: object) -> list[ContextLayer]:
    """Preserve layer selection while keeping resource-key parsing with cache ownership."""
    if isinstance(raw_layers, list) and raw_layers:
        values = [
            str(value).strip().lower() for value in cast(list[object], raw_layers)
        ]
    elif isinstance(raw_layers, str) and raw_layers.strip():
        values = [value.strip().lower() for value in raw_layers.split(",")]
    else:
        values = ["l0", "l1"]
    resolved: list[ContextLayer] = []
    for value in values:
        for layer in ContextLayer:
            if value == layer.value:
                resolved.append(layer)
                break
    if ContextLayer.IDENTITY not in resolved:
        resolved.insert(0, ContextLayer.IDENTITY)
    if ContextLayer.ESSENTIAL not in resolved:
        resolved.insert(1 if resolved else 0, ContextLayer.ESSENTIAL)
    return list(dict.fromkeys(resolved))


def render_context_layer(layer: LayerResult) -> str:
    """Render the existing layer labels without changing layer selection or budgets."""
    if not layer.content.strip():
        return ""
    title_map = {
        ContextLayer.IDENTITY: "### L0 Identity",
        ContextLayer.ESSENTIAL: "### L1 Essential Story",
        ContextLayer.ON_DEMAND: "### L2 On-Demand",
        ContextLayer.DEEP_SEARCH: "### L3 Deep Search",
    }
    return f"{title_map[layer.layer]}\n{layer.content}".strip()
