"""Agent Skill Pack discovery and loading (plan: agent-skills-and-composability).

Single MCP tool skill_pack(operation="discover"|"load") for dynamic skill pack
discovery and loading. Manifests are read from package resources
(cortex/resources/skills/*.json). Consolidated to keep tool count within
MAX_REGISTERED_TOOLS without raising the limit.
"""

import json
import logging
from pathlib import Path
from typing import Literal

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.tools.response_builder import error_response, success_response
from cortex.tools.skill_pack.models import SkillPackManifest

logger = logging.getLogger(__name__)

_skills_dir: Path | None = None


def _get_skills_dir() -> Path:
    """Return the path to the skills manifest directory (package resources)."""
    global _skills_dir
    if _skills_dir is None:
        # cortex/tools/skill_pack/operations.py -> cortex/resources/skills
        _skills_dir = (
            Path(__file__).resolve().parent.parent.parent / "resources" / "skills"
        )
    return _skills_dir


def _load_all_manifests() -> list[SkillPackManifest]:
    """Load all skill pack manifests from the skills directory."""
    skills_dir = _get_skills_dir()
    if not skills_dir.is_dir():
        return []
    manifests: list[SkillPackManifest] = []
    for path in sorted(skills_dir.glob("*.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            manifest = SkillPackManifest.model_validate_json(raw)
            manifests.append(manifest)
        except (OSError, ValueError) as e:
            logger.debug("_load_all_manifests: skip %s: %s", path.name, e)
            continue
    return manifests


def _score_pack_for_task(manifest: SkillPackManifest, task_description: str) -> int:
    """Score a pack's relevance to task_description (higher = more relevant)."""
    if not task_description or not task_description.strip():
        return 0
    task_lower = task_description.lower().strip()
    score = 0
    if manifest.description and manifest.description.lower() in task_lower:
        score += 2
    for kw in manifest.keywords:
        if kw.lower() in task_lower:
            score += 1
    if manifest.when_to_use and any(
        w in task_lower for w in manifest.when_to_use.lower().split()
    ):
        score += 1
    return score


def _skill_pack_discover_result(task_description: str | None, limit: int) -> str:
    """Validate and run discover; return JSON string."""
    desc = (task_description or "").strip()
    if not desc:
        return json.dumps(
            error_response(
                error="task_description required when operation is discover",
            ),
            indent=2,
        )
    return _do_discover(desc, limit)


def _skill_pack_load_result(pack_name: str | None) -> str:
    """Validate and run load; return JSON string."""
    name = (pack_name or "").strip()
    if not name:
        return json.dumps(
            error_response(
                error="pack_name required when operation is load",
            ),
            indent=2,
        )
    return _do_load(name)


def _do_discover(task_description: str, limit: int = 5) -> str:
    """Recommend skill packs relevant to a task description. Internal helper."""
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10
    manifests = _load_all_manifests()
    scored: list[tuple[int, SkillPackManifest]] = [
        (_score_pack_for_task(m, task_description), m) for m in manifests
    ]
    scored.sort(key=lambda x: (-x[0], x[1].name))
    recommended = [s[1] for s in scored if s[0] > 0][:limit]
    if not recommended and manifests:
        recommended = [scored[0][1]] if scored else []
    result = success_response(
        task_description=task_description,
        count=len(recommended),
        packs=[
            {
                "name": m.name,
                "description": m.description,
                "reason": (
                    "Keywords or description match"
                    if _score_pack_for_task(m, task_description) > 0
                    else "Default recommendation"
                ),
            }
            for m in recommended
        ],
    )
    return json.dumps(result, indent=2)


def _do_load(pack_name: str) -> str:
    """Load a skill pack by name. Internal helper."""
    manifests = _load_all_manifests()
    name_lower = pack_name.strip().lower()
    for m in manifests:
        if m.name.lower() == name_lower:
            return json.dumps(
                success_response(pack=m.model_dump(mode="json")),
                indent=2,
            )
    return json.dumps(
        error_response(
            error=f"Skill pack not found: {pack_name}",
            available=[m.name for m in manifests],
        ),
        indent=2,
    )


# Internalized for tool budget reduction (2026-02-26). Kept as callable for tests and internal use.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def skill_pack(
    operation: Literal["discover", "load"],
    task_description: str | None = None,
    pack_name: str | None = None,
    limit: int = 5,
) -> str:
    """Discover skill packs for a task or load a pack by name.

    USE WHEN: For \"discover\" — agent wants to know which skill packs are
    relevant for the current task. For \"load\" — agent wants full guidance
    for a pack (tools, workflows, examples, troubleshooting).

    EXAMPLES: skill_pack(operation=\"discover\", task_description=\"implement feature\"),
    skill_pack(operation=\"load\", pack_name=\"core\").

    RETURNS: For discover — JSON with status, count, and recommended packs.
    For load — JSON with status and full manifest or error.

    Args:
        operation: \"discover\" or \"load\".
        task_description: Required for discover. Natural language task to match
            against pack keywords and descriptions.
        pack_name: Required for load. Pack name (e.g. \"core\", \"quality\").
            Case-insensitive.
        limit: Max packs to return for discover (1–10, default 5).

    Example (discover):
        >>> await skill_pack(operation="discover", task_description="implement feature", limit=3)
        {
          "status": OperationStatus.SUCCESS.value,
          "operation": "discover",
          "count": 2,
          "packs": [
            {"name": "core", "relevance": 0.92, "description": "Core implementation workflows"},
            {"name": "quality", "relevance": 0.75, "description": "Code quality and pre-commit"}
          ]
        }

    Example (load):
        >>> await skill_pack(operation="load", pack_name="core")
        {
          "status": OperationStatus.SUCCESS.value,
          "operation": "load",
          "pack_name": "core",
          "manifest": {"tools": [...], "workflows": [...], "examples": [...]}
        }

    Example (error — unknown operation):
        >>> await skill_pack(operation="other")
        {"status": OperationStatus.ERROR.value, "error": "Unknown operation: 'other'. Use discover or load."}
    """
    op = (operation or "").strip().lower()
    if op == "discover":
        return _skill_pack_discover_result(task_description, limit)
    if op == "load":
        return _skill_pack_load_result(pack_name)
    return json.dumps(
        error_response(
            error=f"Unknown operation: {operation!r}. Use discover or load.",
        ),
        indent=2,
    )
