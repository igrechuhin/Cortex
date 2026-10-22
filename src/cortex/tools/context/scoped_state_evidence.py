"""Goal, rule, and decision evidence without promoting recommendations to authority."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from cortex.core.artifact_graph import normalize_plan_slug
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_change_history import extract_markdown_section
from cortex.core.session_goal_models import SessionGoal
from cortex.core.session_goal_store import session_goal_path
from cortex.tools.context.scoped_snapshot import ScopedSnapshot
from cortex.tools.context.scoped_source_state import ScopedSourceState


def capture_goal_evidence(snapshot: ScopedSnapshot) -> None:
    key = "session-goal"
    try:
        text = snapshot.read(session_goal_path(snapshot.root), "goal/prohibitions", key)
    except (OSError, UnicodeError):
        snapshot.issue(
            "missing_or_unreadable_goal", [key], "Session goal evidence is unavailable."
        )
        return
    try:
        goal = SessionGoal.model_validate_json(text)
    except ValidationError:
        snapshot.sources[key] = snapshot.sources[key].model_copy(
            update={"state": ScopedSourceState.INVALID}
        )
        snapshot.issue(
            "invalid_goal",
            [key],
            "Session goal does not validate; no authority inferred.",
        )
        return
    snapshot.goal = goal
    snapshot.task.evidence("goal", goal.goal, [key])
    snapshot.task.allowed_files = goal.allowed_files
    snapshot.task.prohibitions = goal.blocked_files
    snapshot.task.prohibition_sources = [key]
    _goal_plan_issues(snapshot, goal)


def _goal_plan_issues(snapshot: ScopedSnapshot, goal: SessionGoal) -> None:
    selected = snapshot.scope.removeprefix("plan:")
    if goal.plan_slug and normalize_plan_slug(goal.plan_slug) != selected:
        snapshot.issue(
            "goal_plan_conflict",
            ["session-goal", f"plan:{selected}"],
            "Goal anchor names a different plan; neither authority is overridden.",
        )
    if not goal.plan_slug:
        return
    _goal_derivation_issues(snapshot, goal, selected)


def _rule_path(
    snapshot: ScopedSnapshot, rule: dict[str, object], payload: dict[str, object]
) -> Path | None:
    filename, origin = rule.get("file"), rule.get("source")
    if not isinstance(filename, str):
        return None
    if origin == "shared" and isinstance(rule.get("category"), str):
        # BELIEF: The category is a string, guarded alongside the shared source tag.
        root = get_cortex_path(snapshot.root, CortexResourceType.SYNAPSE) / "rules"
        candidate = root / str(rule["category"]) / filename
    elif origin == "local":
        status = payload.get("rules_manager_status")
        folder = (
            cast(dict[str, object], status).get("rules_folder")
            if isinstance(status, dict)
            else None
        )
        if not isinstance(folder, str):
            return None
        candidate = snapshot.root / folder / filename
    else:
        candidate = snapshot.root / filename
    return candidate if candidate.resolve().is_relative_to(snapshot.root) else None


def _capture_rule(
    snapshot: ScopedSnapshot,
    rule: dict[str, object],
    payload: dict[str, object],
    index: int,
) -> None:
    content = rule.get("content")
    if not isinstance(content, str) or not content.strip():
        snapshot.issue(
            "invalid_rule",
            ["rules-payload"],
            "Selected rule has no nonempty text content.",
        )
        return
    origin, filename = str(rule.get("source", "unknown")), str(rule.get("file", index))
    key = f"rule:{origin}:{rule.get('category', '')}:{filename}"
    snapshot.add_text(key, content, "rule", f"{origin}:{filename}")
    path = _rule_path(snapshot, rule, payload)
    if path is None:
        snapshot.issue(
            "missing_rule_provenance",
            [key],
            "Selected rule has no resolvable original file identity.",
        )
        return
    _capture_rule_source(snapshot, key, path, content)


def capture_rule_evidence(snapshot: ScopedSnapshot, rules_payload: str) -> None:
    snapshot.rules = rules_payload
    snapshot.add_text(
        "rules-payload", rules_payload, "rules", "cortex://rules selected response"
    )
    payload = _decode_rule_payload(snapshot, rules_payload)
    if payload is None:
        return
    rules = payload.get("rules")
    if not isinstance(rules, list):
        snapshot.issue(
            "missing_rules",
            ["rules-payload"],
            "Rules response has no selected rule list.",
        )
        return
    for index, rule in enumerate(cast(list[object], rules)):
        if isinstance(rule, dict):
            _capture_rule(snapshot, cast(dict[str, object], rule), payload, index)


def capture_task_summaries(snapshot: ScopedSnapshot, config: dict[str, object]) -> None:
    slug = snapshot.scope.removeprefix("plan:")
    text = snapshot.plans.get(slug, "")
    _capture_plan_summaries(snapshot, slug, text)
    raw = config.get("explore_log_path")
    keys = [
        key
        for key, path in snapshot.paths.items()
        if isinstance(raw, str) and path.resolve() == (snapshot.root / raw).resolve()
    ]
    decision_text = snapshot.texts.get(keys[0], "") if keys else ""
    open_decisions = extract_markdown_section(decision_text, "## Open Decisions")
    snapshot.task.evidence("open_decisions", _compact(open_decisions), keys)
    snapshot.task.evidence(
        "decision_summary", snapshot.summaries.get("explore_summary"), keys
    )
    if not open_decisions:
        snapshot.issue(
            "missing_open_decisions",
            keys,
            "No explicit open-decision section; recommendations do not establish approval or closure.",
        )


def _compact(text: str | None) -> str | None:
    return " ".join(text.split())[:400] if text else None


def _goal_derivation_issues(
    snapshot: ScopedSnapshot, goal: SessionGoal, selected: str
) -> None:
    if goal.source_plan_revision is None or goal.source_plan_path is None:
        snapshot.issue(
            "missing_goal_provenance",
            ["session-goal"],
            "Legacy goal has no derivation revision.",
        )
        return
    source = snapshot.sources.get(f"plan:{selected}")
    selected_path = snapshot.paths.get(f"plan:{selected}")
    if (
        selected_path is None
        or Path(goal.source_plan_path).resolve() != selected_path.resolve()
    ):
        snapshot.issue(
            "goal_plan_source_conflict",
            ["session-goal", f"plan:{selected}"],
            "Goal derivation path differs from selected plan identity.",
        )
    elif source is not None and source.revision != goal.source_plan_revision:
        snapshot.issue(
            "stale_goal_derivation",
            ["session-goal", f"plan:{selected}"],
            "Plan bytes changed after goal scope derivation; anchor retained unchanged.",
        )


def _capture_rule_source(
    snapshot: ScopedSnapshot, key: str, path: Path, content: str
) -> None:
    try:
        original = snapshot.read(path, "rule-source", f"source:{key}")
    except (OSError, UnicodeError):
        snapshot.issue(
            "missing_rule_source", [key], "Original selected rule file is unavailable."
        )
        return
    # AI: The canonical loaders translate universal newlines but retain the complete text.
    normalized_source = original.replace("\r\n", "\n").replace("\r", "\n")
    if content != normalized_source:
        snapshot.issue(
            "stale_rule_payload",
            [key, f"source:{key}"],
            "Delivered rule text disagrees with original bytes; no implicit replacement.",
        )


def _decode_rule_payload(
    snapshot: ScopedSnapshot, rules_payload: str
) -> dict[str, object] | None:
    try:
        raw: object = json.loads(rules_payload)
    except json.JSONDecodeError:
        snapshot.issue(
            "missing_rule_provenance",
            ["rules-payload"],
            "Plain markdown rules have no original source metadata.",
        )
        return None
    if not isinstance(raw, dict):
        snapshot.issue(
            "invalid_rules_payload",
            ["rules-payload"],
            "Rules response is not an object.",
        )
        return None
    return cast(dict[str, object], raw)


def _capture_plan_summaries(snapshot: ScopedSnapshot, slug: str, text: str) -> None:
    goal = extract_markdown_section(text, "## Goal")
    snapshot.task.evidence("plan_goal", _compact(goal), [f"plan:{slug}"])
    scope = extract_markdown_section(text, "## Scope") or ""
    prohibited = extract_markdown_section(text, "## Prohibitions")
    if prohibited is None and "**out_of_scope**" in scope:
        prohibited = scope.split("**out_of_scope**", 1)[1].lstrip(":\n ")
    snapshot.task.evidence("plan_prohibitions", _compact(prohibited), [f"plan:{slug}"])
    if snapshot.goal is None:
        snapshot.task.evidence("goal", _compact(goal), [f"plan:{slug}"])
    elif goal and " ".join(snapshot.goal.goal.split()) != " ".join(goal.split()):
        snapshot.issue(
            "goal_text_difference",
            ["session-goal", f"plan:{slug}"],
            "Session goal and plan goal differ; both are retained without inferring which instruction governs.",
        )
