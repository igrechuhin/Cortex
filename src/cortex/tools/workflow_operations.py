"""Workflow template suggestion (plan: agent-skills-and-composability Step 4).

Loads YAML workflow templates from package resources and provides
suggest_workflow(task_description) for workflow discovery.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp
from cortex.tools.workflow_models import WorkflowTemplate

_workflows_dir: Path | None = None


def _get_workflows_dir() -> Path:
    """Return the path to the workflows template directory (package resources)."""
    global _workflows_dir
    if _workflows_dir is None:
        _workflows_dir = (
            Path(__file__).resolve().parent.parent / "resources" / "workflows"
        )
    return _workflows_dir


def _load_all_workflows() -> list[WorkflowTemplate]:
    """Load all workflow templates from the workflows directory."""
    wdir = _get_workflows_dir()
    if not wdir.is_dir():
        return []
    templates: list[WorkflowTemplate] = []
    for path in sorted(wdir.glob("*.yaml")):
        try:
            raw = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                templates.append(WorkflowTemplate.model_validate(data))
        except Exception:
            continue
    return templates


def _score_workflow_for_task(template: WorkflowTemplate, task: str) -> int:
    """Score a workflow's relevance to task (higher = more relevant)."""
    if not task or not task.strip():
        return 0
    task_lower = task.lower().strip()
    score = 0
    if template.description and template.description.lower() in task_lower:
        score += 2
    for kw in template.keywords:
        if kw.lower() in task_lower:
            score += 1
    return score


def _recommended_workflows(
    templates: list[WorkflowTemplate], task: str, limit: int
) -> list[WorkflowTemplate]:
    """Return recommended workflows for task, up to limit."""
    scored: list[tuple[int, WorkflowTemplate]] = [
        (_score_workflow_for_task(t, task), t) for t in templates
    ]
    scored.sort(key=lambda x: (-x[0], x[1].name))
    recommended = [s[1] for s in scored if s[0] > 0][:limit]
    if not recommended and templates:
        recommended = [scored[0][1]] if scored else []
    return recommended


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=read_only_annotations(
        "Suggest Workflow",
        idempotent=True,
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def suggest_workflow(
    task_description: str,
    limit: int = 3,
) -> str:
    """Recommend workflow templates relevant to a task description.

    USE WHEN: Agent wants guidance on which tool sequence to follow
    for the current task (implement, debug, quality, handoff).

    EXAMPLES: suggest_workflow(task_description="implement new API"),
    suggest_workflow(task_description="fix failing tests", limit=2).

    RETURNS: JSON with status and recommended workflows (name, description, steps).
    Templates are guidance only; agent adapts the sequence as needed.

    Args:
        task_description: Short description of the current task or goal.
        limit: Maximum number of workflows to return (default 3, max 10).

    Returns:
        JSON string with status and list of recommended workflows.

    Example:
        >>> suggest_workflow(task_description="implement new API", limit=2)
        {"status": "success", "task_description": "implement new API", "count": 2,
         "workflows": [{"name": "Implement", "description": "...", "steps": ["Load context", ...]}, ...]}
    """
    limit = max(1, min(10, limit))
    templates = _load_all_workflows()
    task = task_description.strip() if task_description else ""
    recommended = _recommended_workflows(templates, task, limit)
    return json.dumps(
        {
            "status": "success",
            "task_description": task or "(none)",
            "count": len(recommended),
            "workflows": [
                {"name": t.name, "description": t.description, "steps": t.steps}
                for t in recommended
            ],
        },
        indent=2,
    )
