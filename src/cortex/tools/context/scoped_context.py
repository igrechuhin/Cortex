"""Scoped context packet assembly for plan-targeted context loads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from cortex.core.artifact_graph import resolve_upstream_plans
from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_change_history import last_change_context_line
from cortex.core.rules_filter import filter_rules
from cortex.core.task_classifier import infer_task_type

# Match file paths with known source/config extensions mentioned in plan text.
_FILE_PATH_RE = re.compile(
    (
        r"(?:^|[\s,])("
        + r"(?:src|tests?|docs?|\.cortex|\.claude|\.cursor)/[^\s,)>\"']+"
        + r"\.(?:py|ts|tsx|js|jsx|go|rs|swift|kt|java|rb|cs|md|yml|yaml|toml|json)"
        + r")"
    ),
    re.MULTILINE,
)


def _load_plan_text(plans_dir: Path, slug: str) -> str | None:
    path = plans_dir / f"{slug}.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _estimate_tokens(text: str) -> int:
    # AI: Fast heuristic avoids expensive tokenizer dependency in hot path.
    return max(1, len(text.split()))


def _build_context_stats(
    upstream_plans: list[dict[str, str]],
    current_plan: dict[str, str],
    filtered_rules: str,
    rules_sections_included: int,
    rules_sections_total: int,
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
        "rules_sections_included": rules_sections_included,
        "rules_sections_total": rules_sections_total,
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
) -> dict[str, object] | None:
    """Build scoped context packet for scope='plan:<slug>'."""
    slug = _parse_plan_scope(scope)
    if slug is None:
        return None
    plans_dir = get_cortex_path(project_root, CortexResourceType.PLANS)
    current_plan_text = _load_plan_text(plans_dir, slug)
    if current_plan_text is None:
        return {"scope": scope, "error": f"Plan not found: {slug}"}
    return _assemble_scoped_packet(
        scope, slug, current_plan_text, plans_dir, rules_payload
    )


def _parse_plan_scope(scope: str) -> str | None:
    if not scope.startswith("plan:"):
        return None
    slug = scope.split(":", 1)[1].strip()
    return slug or None


def _load_upstream_plan_content(plans_dir: Path, slug: str) -> list[dict[str, str]]:
    upstream_plans: list[dict[str, str]] = []
    for upstream_slug in resolve_upstream_plans(slug, plans_dir):
        text = _load_plan_text(plans_dir, upstream_slug)
        if text is not None:
            upstream_plans.append({"slug": upstream_slug, "content": text})
    return upstream_plans


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
    scope: str,
    slug: str,
    current_plan_text: str,
    plans_dir: Path,
    rules_payload: str,
) -> dict[str, object]:
    upstream_plans = _load_upstream_plan_content(plans_dir, slug)
    files_touched = extract_file_paths(current_plan_text)
    task_types = infer_task_type(current_plan_text, files_touched=files_touched)
    filtered_rules = filter_rules(rules_payload, task_types)
    total_sections = _count_rules_sections(rules_payload)
    included_sections = _count_rules_sections(filtered_rules)
    current_plan, stats_plan = _current_plan_and_stats_payloads(slug, current_plan_text)
    return {
        "scope": scope,
        "task_types": [task_type.value for task_type in task_types],
        "upstream_plans": upstream_plans,
        "current_plan": current_plan,
        "filtered_rules": filtered_rules,
        "context_stats": _build_context_stats(
            upstream_plans,
            stats_plan,
            filtered_rules,
            included_sections,
            total_sections,
        ),
    }


def append_scoped_context_payload(
    payload_data: ModelDict,
    *,
    project_root: Path,
    session_config: dict[str, object],
    rules_payload: str,
) -> ModelDict:
    """Attach scoped context packet when session config includes plan scope."""
    resolved_scope = _resolve_scope_from_session_config(session_config)
    if resolved_scope is None:
        return payload_data
    scoped_packet = build_scoped_context_packet(
        project_root=project_root,
        scope=resolved_scope,
        rules_payload=rules_payload,
    )
    if scoped_packet is None:
        return payload_data
    payload_data["scoped_context"] = cast(JsonValue, scoped_packet)
    return payload_data


def _resolve_scope_from_session_config(session_config: dict[str, object]) -> str | None:
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
