"""Workflow template suggestion (plan: agent-skills-and-composability Step 4).

Loads YAML workflow templates from package resources and provides
suggest_workflow(task_description) for workflow discovery.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from cortex.tools.execution.workflow_models import WorkflowTemplate

logger = logging.getLogger(__name__)

_workflows_dir: Path | None = None


def _get_workflows_dir() -> Path:
    """Return the path to the workflows template directory (package resources)."""
    global _workflows_dir
    if _workflows_dir is None:
        _workflows_dir = (
            Path(__file__).resolve().parent.parent.parent / "resources" / "workflows"
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
        except Exception as e:
            logger.debug("Skipping invalid workflow template %s: %s", path, e)
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


async def suggest_workflow_impl(
    task_description: str,
    limit: int = 3,
) -> str:
    """Recommend workflow templates relevant to a task description.

    Implementation used by run_composite_workflow(operation="suggest_workflow"). See
    run_composite_workflow docstring for public API.
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
