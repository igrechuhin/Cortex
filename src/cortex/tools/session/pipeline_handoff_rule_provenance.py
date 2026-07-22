"""Coverage-checked ``rule_provenance`` operations for ``pipeline_handoff``.

Exposes the "why does this rule exist" read API and provenance-recording
operations from plan ``synapse-rule-provenance.md``: agents record evidence
citations when a rule recommendation is accepted (``record_rule_provenance``),
refresh recency when the cited failure class recurs (``refresh_rule_matches``),
and query justification/staleness (``rule_evidence``, ``pruning_candidates``).

Mirrors ``pipeline_handoff_analytics.py``'s sync/coverage-check pattern.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.experience.recorder import experience_db_path
from cortex.experience.store_core import ExperienceStoreCore

DEFAULT_STALENESS_WINDOW_DAYS = 90.0


def _open_core(project_root: Path) -> ExperienceStoreCore | None:
    db_path = experience_db_path(project_root)
    if not db_path.exists():
        return None
    return ExperienceStoreCore(db_path)


def _no_coverage_response(**extra: object) -> str:
    payload: dict[str, object] = {"status": "no_coverage", "coverage": False}
    payload.update(extra)
    return json.dumps(payload, indent=2)


def _parse_payload(data_str: str | None) -> dict[str, object]:
    if not data_str:
        return {}
    try:
        parsed = json.loads(data_str)
    except json.JSONDecodeError:
        return {}
    return cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}


def _missing_field_error(field: str) -> str:
    return json.dumps({"status": "error", "error": f"{field} is required"}, indent=2)


def op_record_rule_provenance(
    project_root: Path, session_id: str, data_str: str | None
) -> str:
    """Persist evidence citations for a rule recommendation from session pairs."""
    payload = _parse_payload(data_str)
    rule_id = payload.get("rule_id")
    failure_class = payload.get("failure_class")
    if not isinstance(rule_id, str) or not rule_id:
        return _missing_field_error("rule_id")
    if not isinstance(failure_class, str) or not failure_class:
        return _missing_field_error("failure_class")
    core = _open_core(project_root)
    if core is None:
        return _no_coverage_response(recorded=0)
    pairs = core.preference_pairs(session_id)
    pair_ids = payload.get("pair_ids")
    if isinstance(pair_ids, list) and pair_ids:
        wanted = {str(pid) for pid in cast(list[object], pair_ids)}
        pairs = [pair for pair in pairs if pair.failed_node.id in wanted]
    if not pairs:
        return json.dumps({"status": "ok", "recorded": 0, "provenance": None}, indent=2)
    provenance = core.record_rule_provenance(rule_id, pairs, failure_class)
    return json.dumps(
        {
            "status": "ok",
            "recorded": len(pairs),
            "provenance": provenance.model_dump(mode="json") if provenance else None,
        },
        indent=2,
    )


def op_refresh_rule_matches(project_root: Path, session_id: str) -> str:
    """Bump last_matched for rules whose cited failure class recurs in new pairs."""
    core = _open_core(project_root)
    if core is None:
        return _no_coverage_response(refreshed=[])
    pairs = core.preference_pairs(session_id)
    refreshed = core.refresh_rule_matches(pairs)
    return json.dumps({"status": "ok", "refreshed": refreshed}, indent=2)


def op_rule_evidence(project_root: Path, data_str: str | None) -> str:
    """Cited pairs with artifact refs for "why does this rule exist"."""
    payload = _parse_payload(data_str)
    rule_id = payload.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id:
        return _missing_field_error("rule_id")
    core = _open_core(project_root)
    if core is None:
        return _no_coverage_response(evidence=[])
    evidence = core.rule_evidence(rule_id)
    return json.dumps(
        {
            "status": "ok",
            "coverage": bool(evidence),
            "evidence": [link.model_dump(mode="json") for link in evidence],
        },
        indent=2,
    )


def dispatch(
    project_root: Path, operation: str, session_id: str, data_str: str | None
) -> str | None:
    """Route one of the 4 rule-provenance operations to its handler.

    Returns ``None`` for any other operation so the caller can fall through
    to the next dispatcher (mirrors ``pipeline_handoff_analytics.py``'s
    dispatch contract).
    """
    if operation == "rule_evidence":
        return op_rule_evidence(project_root, data_str)
    if operation == "pruning_candidates":
        return op_pruning_candidates(project_root, data_str)
    if operation == "record_rule_provenance":
        return op_record_rule_provenance(project_root, session_id, data_str)
    if operation == "refresh_rule_matches":
        return op_refresh_rule_matches(project_root, session_id)
    return None


def op_pruning_candidates(project_root: Path, data_str: str | None) -> str:
    """Rules whose cited failure class has had zero matches within the window."""
    payload = _parse_payload(data_str)
    window_raw = payload.get("window_days")
    window_days = (
        float(cast(float, window_raw))
        if isinstance(window_raw, int | float)
        else DEFAULT_STALENESS_WINDOW_DAYS
    )
    core = _open_core(project_root)
    if core is None:
        return _no_coverage_response(candidates=[])
    candidates = core.pruning_candidates(window_days)
    return json.dumps(
        {
            "status": "ok",
            "window_days": window_days,
            "candidates": [c.model_dump(mode="json") for c in candidates],
        },
        indent=2,
    )
