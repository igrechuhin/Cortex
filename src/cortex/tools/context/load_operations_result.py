"""
Phase 4: Context loading result formatting and logging.

Formats load_context results and emits context call logs for effectiveness analysis.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.models import ContextDepth, JsonValue, ModelDict
from cortex.core.session_logger import log_load_context_call
from cortex.optimization.agent_roles import AgentRole
from cortex.optimization.optimization_strategies import OptimizationResult
from cortex.tools.context.load_models import FileMapEntry
from cortex.tools.metadata_logging_helpers import log_metadata_context_call


def format_load_context_result(
    task_description: str,
    token_budget: int,
    strategy: str,
    result: OptimizationResult,
    depth: ContextDepth = ContextDepth.FULL,
) -> str:
    """Format load context result as JSON.

    Args:
        task_description: Task description
        token_budget: Token budget used
        strategy: Strategy used
        result: Context loading result
        depth: Content depth level used

    Returns:
        JSON string with loaded context results
    """
    depth_str = depth.value
    response_data = {
        "status": "success",
        "task_description": task_description,
        "token_budget": token_budget,
        "strategy": strategy,
        "depth": depth_str,
        "selected_files": result.selected_files,
        "selected_sections": result.selected_sections,
        "total_tokens": result.total_tokens,
        "utilization": round(result.utilization, 2),
        "excluded_files": result.excluded_files,
        "relevance_scores": result.metadata.get("relevance_scores", {}),
    }

    if depth == ContextDepth.METADATA_ONLY and "files" in result.metadata:
        response_data["files"] = result.metadata["files"]

    return json.dumps(response_data, indent=2)


def log_context_call(
    project_root: Path,
    task_description: str,
    token_budget: int,
    strategy: str,
    result: OptimizationResult,
    agent_role: AgentRole | None = None,
) -> None:
    """Log load_context call for effectiveness analysis.

    Args:
        project_root: Project root path
        task_description: Task description
        token_budget: Token budget used
        strategy: Strategy used
        result: Context loading result
        agent_role: Optional agent role for role-aware logging
    """
    raw_scores: JsonValue = result.metadata.get("relevance_scores", {})
    scores: dict[str, float] = {}
    if isinstance(raw_scores, dict):
        typed_scores = cast(ModelDict, raw_scores)
        for file_name, score_value in typed_scores.items():
            if isinstance(score_value, (int, float)):
                scores[file_name] = float(score_value)

    role_str: str | None = None
    if agent_role is not None:
        role_str = agent_role.value

    log_load_context_call(
        project_root=project_root,
        task_description=task_description,
        token_budget=token_budget,
        strategy=strategy,
        selected_files=result.selected_files,
        selected_sections=result.selected_sections,
        total_tokens=result.total_tokens,
        utilization=result.utilization,
        excluded_files=result.excluded_files,
        relevance_scores=scores,
        role=role_str,
    )


def emit_metadata_only_log(
    project_root: Path,
    task_description: str,
    token_budget: int,
    strategy: str,
    files_map: list[FileMapEntry],
    always_loaded_content: dict[str, str],
    always_load_sections: dict[str, list[str]],
    files_metadata: dict[str, ModelDict],
    always_loaded_tokens: int,
    relevance_scores: dict[str, float],
    agent_role: AgentRole | None,
) -> None:
    """Emit metadata-only context load log."""
    log_metadata_context_call(
        project_root,
        task_description,
        token_budget,
        strategy,
        files_map,
        always_loaded_content,
        always_load_sections,
        files_metadata,
        always_loaded_tokens,
        relevance_scores,
        agent_role,
    )
