"""Logging helpers for Phase 4 metadata context loading.

Extracted from metadata_helpers to keep the main module under 400 lines.
"""

from pathlib import Path

from cortex.core.models import ModelDict
from cortex.core.session_logger import log_load_context_call
from cortex.optimization.agent_roles import AgentRole
from cortex.tools.context_models import FileMapEntry
from cortex.tools.metadata_helpers import (
    calculate_metadata_tokens,
    extract_selected_files_from_map,
)


def extract_metadata_logging_info(
    files_map: list[FileMapEntry],
    always_loaded_content: dict[str, str],
    always_load_sections: dict[str, list[str]],
    files_metadata: dict[str, ModelDict],
    always_loaded_tokens: int,
    token_budget: int,
) -> tuple[list[str], dict[str, list[str]], list[str], int, float]:
    """Extract logging information from metadata-only context.

    Returns:
        Tuple of (selected_files, selected_sections, excluded_files, total_tokens, utilization)
    """
    selected_files, selected_sections = extract_selected_files_from_map(files_map)
    selected_files.extend(list(always_loaded_content.keys()))
    for file_name, sections_dict in always_load_sections.items():
        if file_name not in selected_sections:
            selected_sections[file_name] = sections_dict
    all_metadata_files = set(files_metadata.keys())
    excluded_files = list(all_metadata_files - set(selected_files))
    metadata_tokens = calculate_metadata_tokens(files_map)
    total_tokens = metadata_tokens + always_loaded_tokens
    utilization = round(total_tokens / token_budget, 2) if token_budget > 0 else 0.0
    return selected_files, selected_sections, excluded_files, total_tokens, utilization


def _prepare_logging_params(
    files_map: list[FileMapEntry],
    always_loaded_content: dict[str, str],
    always_load_sections: dict[str, list[str]],
    files_metadata: dict[str, ModelDict],
    always_loaded_tokens: int,
    token_budget: int,
) -> tuple[list[str], dict[str, list[str]], list[str], int, float]:
    """Prepare logging parameters from metadata context."""
    return extract_metadata_logging_info(
        files_map,
        always_loaded_content,
        always_load_sections,
        files_metadata,
        always_loaded_tokens,
        token_budget,
    )


def _invoke_load_context_log(
    project_root: Path,
    task_description: str,
    token_budget: int,
    strategy: str,
    selected_files: list[str],
    selected_sections: dict[str, list[str]],
    total_tokens: int,
    utilization: float,
    excluded_files: list[str],
    relevance_scores: dict[str, float],
    role: str | None,
) -> None:
    """Call session logger with prepared params."""
    log_load_context_call(
        project_root,
        task_description,
        token_budget,
        strategy,
        selected_files,
        selected_sections,
        total_tokens,
        utilization,
        excluded_files,
        relevance_scores,
        role,
    )


def _emit_metadata_context_log(
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
    """Prepare logging params and emit metadata-only context log."""
    selected_files, selected_sections, excluded_files, total_tokens, utilization = (
        _prepare_logging_params(
            files_map,
            always_loaded_content,
            always_load_sections,
            files_metadata,
            always_loaded_tokens,
            token_budget,
        )
    )
    # fmt: off
    _invoke_load_context_log(project_root, task_description, token_budget, strategy, selected_files, selected_sections, total_tokens, utilization, excluded_files, relevance_scores, agent_role.value if agent_role else None)
    # fmt: on


def log_metadata_context_call(
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
    """Log metadata-only context loading call."""
    _emit_metadata_context_log(
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
