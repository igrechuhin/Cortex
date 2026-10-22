"""Scoped context packet assembly for plan-targeted context loads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.core.plan_change_history import last_change_context_line
from cortex.core.rules_filter import filter_rules
from cortex.core.task_classifier import infer_task_type
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

# Match file paths with known source/config extensions mentioned in plan text.
_FILE_PATH_RE = re.compile(
    (
        r"(?:^|[\s,])("
        + r"(?:src|tests?|docs?|\.cortex|\.claude)/[^\s,)>\"']+"
        + r"\.(?:py|ts|tsx|js|jsx|go|rs|swift|kt|java|rb|cs|md|yml|yaml|toml|json)"
        + r")"
    ),
    re.MULTILINE,
)


def _estimate_tokens(text: str) -> int:
    # AI: Fast heuristic avoids expensive tokenizer dependency in hot path.
    return max(1, len(text.split()))


def _build_context_stats(
    upstream_plans: list[dict[str, str]],
    current_plan: dict[str, str],
    filtered_rules: str,
    rules_payload: str,
) -> dict[str, object]:
    upstream_text = "\n".join(plan["content"] for plan in upstream_plans)
    sections = {
        "upstream_plans": _estimate_tokens(upstream_text) if upstream_text else 0,
        "current_plan": _estimate_tokens(current_plan["content"]),
        "rules": _estimate_tokens(filtered_rules),
    }
    return {
        "total_tokens_estimate": sum(sections.values()),
        "sections": sections,
        "rules_sections_included": _count_rules_sections(filtered_rules),
        "rules_sections_total": _count_rules_sections(rules_payload),
    }


def _count_rules_sections(rules_content: str) -> int:
    return sum(1 for line in rules_content.splitlines() if line.startswith("## "))


def extract_file_paths(plan_text: str) -> list[str]:
    """Extract file paths mentioned in plan text for file-path-based classification."""
    return list(dict.fromkeys(m.group(1) for m in _FILE_PATH_RE.finditer(plan_text)))


def build_scoped_context_packet(
    *,
    project_root: Path,
    scope: str,
    rules_payload: str,
    snapshot: ScopedSnapshot | None = None,
) -> dict[str, object] | None:
    """Build scoped context packet for scope='plan:<slug>'."""
    slug = _parse_plan_scope(scope)
    if slug is None:
        return None
    if snapshot is None:
        snapshot = _capture_default_snapshot(project_root, slug, rules_payload)
    revision_payload = _scoped_revision_payload(snapshot)
    packet = _assemble_scoped_packet(snapshot, slug, rules_payload)
    packet.update(revision_payload)
    return packet


def _parse_plan_scope(scope: str) -> str | None:
    if not scope.startswith("plan:"):
        return None
    slug = scope.split(":", 1)[1].strip()
    return slug or None


def _current_plan_and_stats_payloads(
    slug: str, plan_text: str
) -> tuple[dict[str, object], dict[str, str]]:
    last_change = last_change_context_line(plan_text)
    current_plan: dict[str, object] = {"slug": slug, "content": plan_text}
    if last_change is not None:
        current_plan["last_change"] = last_change
    stats_plan: dict[str, str] = {"slug": slug, "content": plan_text}
    return current_plan, stats_plan


def _assemble_scoped_packet(
    snapshot: ScopedSnapshot,
    slug: str,
    rules_payload: str,
) -> dict[str, object]:
    current_plan_text = snapshot.plans.get(slug)
    if current_plan_text is None:
        return {
            "scope": snapshot.scope,
            "error": f"Plan not found or ambiguous: {slug}",
        }
    upstream_plans = _upstream_plan_payloads(snapshot)
    files_touched = extract_file_paths(current_plan_text)
    task_types = infer_task_type(current_plan_text, files_touched=files_touched)
    filtered_rules = filter_rules(rules_payload, task_types)
    current_plan, stats_plan = _current_plan_and_stats_payloads(slug, current_plan_text)
    return {
        "scope": snapshot.scope,
        "task_types": [task_type.value for task_type in task_types],
        "upstream_plans": upstream_plans,
        "current_plan": current_plan,
        "filtered_rules": filtered_rules,
        "context_stats": _build_context_stats(
            upstream_plans,
            stats_plan,
            filtered_rules,
            rules_payload,
        ),
    }


def append_scoped_context_payload(
    payload_data: ModelDict,
    *,
    project_root: Path,
    session_config: dict[str, object],
    rules_payload: str,
    snapshot: ScopedSnapshot | None = None,
) -> ModelDict:
    """Attach scoped context packet when session config includes plan scope."""
    resolved_scope = snapshot.scope if snapshot else resolve_plan_scope(session_config)
    if resolved_scope is None:
        return payload_data
    scoped_packet = build_scoped_context_packet(
        project_root=project_root,
        scope=resolved_scope,
        rules_payload=rules_payload,
        snapshot=snapshot,
    )
    if scoped_packet is None:
        return payload_data
    payload_data["scoped_context"] = cast(JsonValue, scoped_packet)
    return payload_data


def resolve_plan_scope(session_config: dict[str, object]) -> str | None:
    scope_raw = session_config.get("scope")
    if isinstance(scope_raw, str) and scope_raw.strip():
        return scope_raw.strip()
    plan_file_raw = session_config.get("plan_file")
    if not isinstance(plan_file_raw, str) or not plan_file_raw.strip():
        return None
    plan_path = Path(plan_file_raw.strip())
    if plan_path.suffix != ".md":
        return None
    return f"plan:{plan_path.stem}"


def _capture_default_snapshot(
    project_root: Path, slug: str, rules_payload: str
) -> ScopedSnapshot:
    snapshot = ScopedSnapshot(root=project_root.resolve(), scope=f"plan:{slug}")
    capture_plan_evidence(snapshot)
    capture_goal_evidence(snapshot)
    capture_rule_evidence(snapshot, rules_payload)
    capture_task_summaries(snapshot, {})
    return snapshot


def _scoped_revision_payload(snapshot: ScopedSnapshot) -> dict[str, object]:
    if not snapshot.files_unchanged() or not plan_membership_unchanged(snapshot):
        snapshot.issue(
            "incoherent_snapshot",
            list(snapshot.sources),
            "Selected input changed during assembly; do not treat this packet as fresh.",
        )
    return {
        "revision_manifest": [
            source.model_dump(mode="json") for source in snapshot.sources.values()
        ],
        "task_state": snapshot.task.model_dump(mode="json"),
        "freshness": (
            "incoherent"
            if any(
                issue.code == "incoherent_snapshot" for issue in snapshot.task.issues
            )
            else "warnings" if snapshot.task.issues else "fresh"
        ),
    }


def _upstream_plan_payloads(snapshot: ScopedSnapshot) -> list[dict[str, str]]:
    return [
        {"slug": upstream, "content": snapshot.plans[upstream]}
        for upstream in snapshot.upstream
    ]
