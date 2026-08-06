"""Context payload appenders and support readers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.context.recent_artifacts_context import (
    build_recent_artifacts_markdown,
)
from cortex.tools.context.recent_ingested_sources_context import (
    build_recent_ingested_sources_markdown,
)
from cortex.tools.context.scoped_context import append_scoped_context_payload
from cortex.tools.session.models import SESSION_SCOPE_PROMPT


def append_session_goal_to_context_payload(payload: str, project_root: Path) -> str:
    """Prepend session_goal to successful context payloads when anchor file exists."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(parsed, dict):
        return payload
    data = cast(dict[str, object], parsed)
    if data.get("status") != "success":
        return payload
    from cortex.core.session_goal_store import read_session_goal

    sg = read_session_goal(project_root)
    if sg is None:
        return payload
    merged: dict[str, object] = {"session_goal": json.loads(sg.model_dump_json())}
    merged.update(data)
    return json.dumps(merged, indent=2, sort_keys=True)


def append_session_scope_to_context_payload(payload: str) -> str:
    """Add session scope guidance to successful context payloads."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(parsed, dict):
        return payload
    payload_data = cast(dict[str, object], parsed)
    if payload_data.get("status") != "success":
        return payload
    payload_data["session_scope"] = SESSION_SCOPE_PROMPT
    return json.dumps(payload_data, indent=2, sort_keys=True)


def _read_recent_operations_lines(project_root: Path) -> str | None:
    """Read up to the last 10 non-empty lines from memory-bank log.md."""
    log_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK) / "log.md"
    if not log_path.exists():
        return None
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    if not lines:
        return None
    return "\n".join(lines[-10:])


def _append_recent_operations_to_context_payload(
    payload: str, recent_operations_lines: str | None
) -> str:
    """Attach a markdown recent-operations section to successful context payloads."""
    if recent_operations_lines is None:
        return payload
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(parsed, dict):
        return payload
    payload_data = cast(dict[str, object], parsed)
    if payload_data.get("status") != "success":
        return payload
    payload_data["recent_operations"] = (
        f"## Recent Operations\n\n{recent_operations_lines}"
    )
    return json.dumps(payload_data, indent=2, sort_keys=True)


def _read_recent_artifacts_markdown(project_root: Path) -> str | None:
    """Build Recent Artifacts markdown from filed pages under memory-bank/reviews|analyses."""
    memory_bank = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return build_recent_artifacts_markdown(memory_bank)


def _append_recent_artifacts_to_context_payload(
    payload: str, recent_artifacts_markdown: str | None
) -> str:
    """Attach a markdown Recent Artifacts section to successful context payloads."""
    if recent_artifacts_markdown is None:
        return payload
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(parsed, dict):
        return payload
    payload_data = cast(dict[str, object], parsed)
    if payload_data.get("status") != "success":
        return payload
    payload_data["recent_artifacts"] = recent_artifacts_markdown
    return json.dumps(payload_data, indent=2, sort_keys=True)


def read_recent_ingested_sources_markdown(project_root: Path) -> str | None:
    """Build Recently Ingested Sources markdown from wiki or memory-bank ``sources/``."""
    from cortex.wiki.ingest_wiki import wiki_ingest_enabled

    memory_bank = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    if wiki_ingest_enabled(wiki_root):
        wiki_sources = wiki_root / "sources"
        if wiki_sources.is_dir() and any(wiki_sources.glob("*.md")):
            wiki_md = build_recent_ingested_sources_markdown(wiki_root)
            if wiki_md is not None:
                return wiki_md
    return build_recent_ingested_sources_markdown(memory_bank)


def _append_recent_ingested_sources_to_context_payload(
    payload: str, recent_ingested_sources_markdown: str | None
) -> str:
    """Attach a markdown Recently Ingested Sources section to successful payloads."""
    if recent_ingested_sources_markdown is None:
        return payload
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(parsed, dict):
        return payload
    payload_data = cast(dict[str, object], parsed)
    if payload_data.get("status") != "success":
        return payload
    payload_data["recent_ingested_sources"] = recent_ingested_sources_markdown
    return json.dumps(payload_data, indent=2, sort_keys=True)


def _read_explore_summary_markdown(project_root: Path) -> str | None:
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    log_path_raw = cfg.get("explore_log_path")
    if not isinstance(log_path_raw, str) or not log_path_raw.strip():
        return None
    explore_path = (project_root / log_path_raw).resolve()
    if not explore_path.is_file():
        return None
    try:
        log_text = explore_path.read_text(encoding="utf-8")
    except OSError:
        return None
    selected = _extract_markdown_section(log_text, "## Selected Option")
    recommendation = _extract_markdown_section(log_text, "## Recommendation")
    if not selected and not recommendation:
        return None
    lines = ["## Explore Summary", f"- Source: `{log_path_raw}`"]
    if selected:
        lines.append(f"- Selected option: {selected.splitlines()[0].strip()}")
    if recommendation:
        lines.append(f"- Recommendation: {recommendation.splitlines()[0].strip()}")
    return "\n".join(lines)


def _extract_markdown_section(markdown: str, heading: str) -> str | None:
    lines = markdown.splitlines()
    in_section = False
    section_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == heading:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section:
            section_lines.append(line)
    content = "\n".join(section_lines).strip()
    return content or None


def _append_explore_summary_to_context_payload(
    payload: str, explore_summary_markdown: str | None
) -> str:
    if explore_summary_markdown is None:
        return payload
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(parsed, dict):
        return payload
    payload_data = cast(dict[str, object], parsed)
    if payload_data.get("status") != "success":
        return payload
    payload_data["explore_summary"] = explore_summary_markdown
    return json.dumps(payload_data, indent=2, sort_keys=True)


def _extract_rules_markdown(rules_payload: str) -> str:
    """Extract merged rules markdown text from cortex://rules JSON payload."""
    try:
        parsed = json.loads(rules_payload)
    except json.JSONDecodeError:
        return rules_payload
    if not isinstance(parsed, dict):
        return rules_payload
    parsed_dict = cast(dict[str, object], parsed)
    rules_raw = parsed_dict.get("rules")
    if not isinstance(rules_raw, list):
        return rules_payload
    chunks: list[str] = []
    for rule_raw in cast(list[object], rules_raw):
        rule = cast(dict[str, object], rule_raw) if isinstance(rule_raw, dict) else None
        if isinstance(rule, dict):
            content = rule.get("content")
            if isinstance(content, str) and content.strip():
                chunks.append(content.strip())
    if not chunks:
        return rules_payload
    return "\n\n".join(chunks)


def _session_config_mapping(session_cfg: object) -> dict[str, object]:
    """Convert SessionConfig-like objects or dicts to plain mappings."""
    if isinstance(session_cfg, dict):
        return cast(dict[str, object], session_cfg)
    to_mapping = getattr(session_cfg, "to_mapping", None)
    if callable(to_mapping):
        mapped = to_mapping()
        if isinstance(mapped, dict):
            return cast(dict[str, object], mapped)
    return {}


def resolve_context_cache_scope() -> str:
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    scope_raw = cfg.get("scope")
    if isinstance(scope_raw, str) and scope_raw.strip():
        return scope_raw.strip()
    plan_file_raw = cfg.get("plan_file")
    if isinstance(plan_file_raw, str) and plan_file_raw.strip():
        return f"plan-file:{Path(plan_file_raw.strip()).name}"
    return ""


async def append_context_scoped_payload(payload: str, project_root: Path) -> str:
    """Attach scoped context packet to successful context payloads."""
    try:
        payload_data = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    payload_dict = (
        cast(dict[str, object], payload_data)
        if isinstance(payload_data, dict)
        else None
    )
    if payload_dict is None or payload_dict.get("status") != "success":
        return payload
    from cortex.core.session_config import read_session_config

    session_cfg = read_session_config()
    from cortex.tools.optimization import handlers as handlers_module

    rules_payload = await handlers_module.get_relevant_rules()
    rules_markdown = _extract_rules_markdown(rules_payload)
    merged = append_scoped_context_payload(
        cast(ModelDict, payload_dict),
        project_root=project_root,
        session_config=_session_config_mapping(session_cfg),
        rules_payload=rules_markdown,
    )
    return json.dumps(merged, indent=2, sort_keys=True)


async def apply_context_payload_appenders(base_payload: str, project_root: Path) -> str:
    """Apply all context appenders to successful base payload."""
    recent_ops = _read_recent_operations_lines(project_root)
    recent_artifacts = _read_recent_artifacts_markdown(project_root)
    recent_ingested_sources = read_recent_ingested_sources_markdown(project_root)
    explore_summary = _read_explore_summary_markdown(project_root)
    with_goal = append_session_goal_to_context_payload(base_payload, project_root)
    scoped = append_session_scope_to_context_payload(with_goal)
    scoped = await append_context_scoped_payload(scoped, project_root)
    return _append_recent_artifacts_to_context_payload(
        _append_recent_operations_to_context_payload(
            _append_explore_summary_to_context_payload(
                _append_recent_ingested_sources_to_context_payload(
                    scoped, recent_ingested_sources
                ),
                explore_summary,
            ),
            recent_ops,
        ),
        recent_artifacts,
    )


def append_recent_operations_to_context_payload(
    payload: str, recent_operations_lines: str | None
) -> str:
    return _append_recent_operations_to_context_payload(
        payload, recent_operations_lines
    )


def append_recent_artifacts_to_context_payload(
    payload: str, recent_artifacts_markdown: str | None
) -> str:
    return _append_recent_artifacts_to_context_payload(
        payload, recent_artifacts_markdown
    )


def append_recent_ingested_sources_to_context_payload(
    payload: str, recent_ingested_sources_markdown: str | None
) -> str:
    return _append_recent_ingested_sources_to_context_payload(
        payload, recent_ingested_sources_markdown
    )


def append_explore_summary_to_context_payload(
    payload: str, explore_summary_markdown: str | None
) -> str:
    return _append_explore_summary_to_context_payload(payload, explore_summary_markdown)


def read_recent_operations_lines(project_root: Path) -> str | None:
    return _read_recent_operations_lines(project_root)


def read_recent_artifacts_markdown(project_root: Path) -> str | None:
    return _read_recent_artifacts_markdown(project_root)


def read_explore_summary_markdown(project_root: Path) -> str | None:
    return _read_explore_summary_markdown(project_root)
