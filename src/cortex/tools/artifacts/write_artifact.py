"""MCP tool for writing allowed skill/rule artifacts."""

import json
from enum import Enum
from pathlib import Path

from pydantic import ValidationError

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import cortex_agent_only_auth, mcp
from cortex.tools.response_builder import error_response, success_response
from cortex.tools.skill_pack.models import SkillPackManifest


class ArtifactType(str, Enum):
    """Artifact types supported by write_artifact."""

    SKILL = "skill"
    RULE = "rule"


def _get_skills_dir() -> Path:
    """Return the package skills resources directory."""
    return Path(__file__).resolve().parent.parent.parent / "resources" / "skills"


def _validate_name(artifact_type: ArtifactType, name: str) -> str:
    candidate = name.strip()
    if not candidate:
        raise ValueError("name must be non-empty")

    path_like = Path(candidate)
    if path_like.is_absolute() or ".." in path_like.parts:
        raise ValueError("name must be a relative path without traversal")

    if artifact_type == ArtifactType.SKILL and ("/" in candidate or "\\" in candidate):
        raise ValueError("skill name must be a slug (no path separators)")

    if artifact_type == ArtifactType.RULE and not candidate.endswith(".mdc"):
        raise ValueError("rule name must end with .mdc")

    return candidate


def _resolve_artifact_path(
    artifact_type: ArtifactType, name: str, project_root: Path
) -> Path:
    safe_name = _validate_name(artifact_type, name)
    if artifact_type == ArtifactType.SKILL:
        return _get_skills_dir() / f"{safe_name}.json"

    synapse_dir = get_cortex_path(project_root, CortexResourceType.SYNAPSE)
    return synapse_dir / "rules" / safe_name


def _validate_rule_content(content: str) -> None:
    text = content.strip()
    if not text:
        raise ValueError("rule content must be non-empty")

    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ValueError("rule content must start with YAML frontmatter")

    closing_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break
    if closing_idx == -1:
        raise ValueError("rule frontmatter is missing closing ---")

    frontmatter_lines = lines[1:closing_idx]
    has_description = any(
        line.split(":", 1)[0].strip() == "description"
        and bool(line.split(":", 1)[1].strip())
        for line in frontmatter_lines
        if ":" in line
    )
    if not has_description:
        raise ValueError("rule frontmatter must include non-empty description")


def _validate_content(artifact_type: ArtifactType, content: str) -> None:
    if artifact_type == ArtifactType.SKILL:
        _ = SkillPackManifest.model_validate_json(content)
        return
    _validate_rule_content(content)


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    _ = tmp_path.write_text(content, encoding="utf-8")
    _ = tmp_path.replace(path)


@mcp.tool(
    annotations=safe_write_annotations("Write Skill or Rule Artifact"),
    auth=cortex_agent_only_auth,
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def write_artifact(
    artifact_type: ArtifactType,
    name: str,
    content: str,
    ctx: MCPContext | None = None,
) -> str:
    """Write a validated skill JSON or rule .mdc file to allowlisted locations.

    USE WHEN: Analysis agents need to persist generated skill manifests under
    ``src/cortex/resources/skills`` or generic, cross-project Synapse rules under
    ``.cortex/synapse/rules`` using an explicit allowlisted write tool.

    RULES ARE GENERIC-ONLY — CRITICAL CONSTRAINT:
    ``artifact_type="rule"`` writes to ``.cortex/synapse/rules/`` which is a SHARED
    submodule visible across ALL projects. ONLY write a rule here when it applies
    verbatim to any project in any codebase (e.g. general security, testing standards).

    DO NOT USE for project-specific patterns — rules derived from THIS project's code,
    architecture, UI components, or conventions. Those belong in ``.cortex/rules/``
    and must be written with the plain Write tool, NOT write_artifact.

    Decision checklist before calling write_artifact for a rule:
    - Would this rule read identically in a different repo? → write_artifact (synapse)
    - Does this rule reference a class/view/pattern from THIS project? → Write to .cortex/rules/

    EXAMPLES:
    - write_artifact(artifact_type="skill", name="commit-pipeline", content="{...}")
    - write_artifact(artifact_type="rule", name="general/no-secrets.mdc", content="---...")
    - write_artifact(artifact_type="rule", name="python/python-async-patterns.mdc", content="---...")
    - NOT: write_artifact for a SwiftUI pattern specific to SideMenuView in this project
    - NOT: write_artifact for a rule referencing this project's Route enum or APIError type
    """
    try:
        project_root = await get_or_resolve_project_root(ctx)
        target_path = _resolve_artifact_path(artifact_type, name, project_root)
        _validate_content(artifact_type, content)
        _write_atomic(target_path, content)
    except (ValueError, ValidationError, OSError) as exc:
        return json.dumps(error_response(error=str(exc)), indent=2)

    return json.dumps(
        success_response(
            artifact_type=artifact_type.value,
            name=name,
            path=str(target_path),
        ),
        indent=2,
    )
