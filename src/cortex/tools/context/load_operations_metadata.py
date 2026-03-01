"""
Phase 4: Context loading metadata-only / hybrid retrieval.

Implements metadata_only depth with hybrid retrieval and role-based scoring.
"""

import json
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ContextDepth, ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.optimization.agent_roles import AgentRole
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.tools.context.load_models import FileMapEntry
from cortex.tools.context.load_operations_result import emit_metadata_only_log
from cortex.tools.hybrid_metadata_helpers import (
    calculate_always_loaded_tokens,
    filter_metadata_excluding_always_loaded,
    load_always_load_sections,
)
from cortex.tools.metadata_helpers import (
    build_files_map_from_metadata,
    calculate_metadata_relevance_scores,
)


async def collect_files_metadata(
    metadata_index: MetadataIndex,
) -> dict[str, ModelDict]:
    """Collect metadata for all files."""
    all_files = await metadata_index.list_all_files()
    files_metadata: dict[str, ModelDict] = {}

    for file_name in all_files:
        metadata_raw = await metadata_index.get_file_metadata(file_name)
        if metadata_raw is not None:
            files_metadata[file_name] = metadata_raw.model_dump(
                mode="json", by_alias=True
            )

    return files_metadata


def build_hybrid_metadata_response(
    task_description: str,
    token_budget: int,
    strategy: str,
    files_map: list[FileMapEntry],
    total_tokens_available: int,
    always_loaded_content: dict[str, str],
    always_loaded_tokens: int,
) -> str:
    """Build hybrid metadata response with always-loaded sections."""
    metadata_tokens = sum(f.total_tokens for f in files_map[:10])
    total_tokens = metadata_tokens + always_loaded_tokens

    response_data = {
        "status": "success",
        "task_description": task_description,
        "token_budget": token_budget,
        "strategy": strategy,
        "depth": ContextDepth.METADATA_ONLY.value,
        "files": [e.model_dump() for e in files_map],
        "total_files": len(files_map),
        "total_tokens_available": total_tokens_available,
        "always_loaded": always_loaded_content,
        "always_loaded_tokens": always_loaded_tokens,
        "total_tokens": total_tokens,
        "utilization": (
            round(total_tokens / token_budget, 2) if token_budget > 0 else 0.0
        ),
    }

    return json.dumps(response_data, indent=2)


async def prepare_metadata_and_relevance(
    metadata_index: MetadataIndex,
    task_description: str,
    agent_role: AgentRole | None = None,
) -> tuple[dict[str, ModelDict], dict[str, float]]:
    """Prepare files metadata and calculate relevance scores."""
    files_metadata = await collect_files_metadata(metadata_index)
    relevance_scores = calculate_metadata_relevance_scores(
        task_description, files_metadata, agent_role
    )
    return files_metadata, relevance_scores


async def load_and_calculate_always_loaded(
    always_load_sections: dict[str, list[str]],
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
) -> tuple[dict[str, str], int]:
    """Load always-loaded sections and calculate tokens."""
    token_counter = TokenCounter()
    always_loaded_content = await load_always_load_sections(
        always_load_sections, metadata_index, fs_manager, token_counter
    )
    always_loaded_tokens = calculate_always_loaded_tokens(
        always_loaded_content, token_counter
    )
    return always_loaded_content, always_loaded_tokens


def build_filtered_files_map(
    files_metadata: dict[str, ModelDict],
    relevance_scores: dict[str, float],
    always_load_sections: dict[str, list[str]],
) -> tuple[list[FileMapEntry], int]:
    """Build files map from filtered metadata."""
    filtered_metadata = filter_metadata_excluding_always_loaded(
        files_metadata, always_load_sections
    )
    return build_files_map_from_metadata(filtered_metadata, relevance_scores)


async def load_always_loaded_and_metadata(
    always_load_sections: dict[str, list[str]],
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    agent_role: AgentRole | None = None,
) -> tuple[dict[str, str], int, dict[str, ModelDict], dict[str, float]]:
    """Load always-loaded content and prepare metadata with role-based scoring."""
    (
        always_loaded_content,
        always_loaded_tokens,
    ) = await load_and_calculate_always_loaded(
        always_load_sections, metadata_index, fs_manager
    )
    files_metadata, relevance_scores = await prepare_metadata_and_relevance(
        metadata_index, task_description, agent_role
    )
    return always_loaded_content, always_loaded_tokens, files_metadata, relevance_scores


def _finalize_hybrid_metadata_context(
    loaded_data: tuple[dict[str, str], int, dict[str, ModelDict], dict[str, float]],
    always_load_sections: dict[str, list[str]],
) -> tuple[
    dict[str, str],
    int,
    dict[str, ModelDict],
    dict[str, float],
    list[FileMapEntry],
    int,
]:
    """Finalize hybrid metadata context from loaded data."""
    always_loaded_content, always_loaded_tokens, files_metadata, relevance_scores = (
        loaded_data
    )
    files_map, total_tokens_available = build_filtered_files_map(
        files_metadata, relevance_scores, always_load_sections
    )
    return (
        always_loaded_content,
        always_loaded_tokens,
        files_metadata,
        relevance_scores,
        files_map,
        total_tokens_available,
    )


async def prepare_hybrid_metadata_context(
    metadata_index: MetadataIndex,
    task_description: str,
    always_load_sections: dict[str, list[str]],
    fs_manager: FileSystemManager,
    agent_role: AgentRole | None = None,
) -> tuple[
    dict[str, str],
    int,
    dict[str, ModelDict],
    dict[str, float],
    list[FileMapEntry],
    int,
]:
    """Prepare hybrid metadata context with role-based scoring."""
    loaded_data = await load_always_loaded_and_metadata(
        always_load_sections, metadata_index, fs_manager, task_description, agent_role
    )
    return _finalize_hybrid_metadata_context(loaded_data, always_load_sections)


def _do_emit_metadata_log(
    project_root: Path,
    task_description: str,
    token_budget: int,
    strategy: str,
    always_load_sections: dict[str, list[str]],
    agent_role: AgentRole | None,
    ctx: tuple[
        dict[str, str],
        int,
        dict[str, ModelDict],
        dict[str, float],
        list[FileMapEntry],
        int,
    ],
) -> None:
    """Invoke emit_metadata_only_log with unpacked ctx."""
    (alc, alt, fm, rs, fmap, _) = ctx
    emit_metadata_only_log(
        project_root,
        task_description,
        token_budget,
        strategy,
        fmap,
        alc,
        always_load_sections,
        fm,
        alt,
        rs,
        agent_role,
    )


def _emit_metadata_log_if_needed(
    project_root: Path | None,
    task_description: str,
    token_budget: int,
    strategy: str,
    always_load_sections: dict[str, list[str]],
    agent_role: AgentRole | None,
    ctx: tuple[
        dict[str, str],
        int,
        dict[str, ModelDict],
        dict[str, float],
        list[FileMapEntry],
        int,
    ],
) -> None:
    """Emit metadata-only log when project_root is set."""
    if project_root is None:
        return
    _do_emit_metadata_log(
        project_root,
        task_description,
        token_budget,
        strategy,
        always_load_sections,
        agent_role,
        ctx,
    )


def _build_response_from_ctx(
    ctx: tuple[
        dict[str, str],
        int,
        dict[str, ModelDict],
        dict[str, float],
        list[FileMapEntry],
        int,
    ],
    task_description: str,
    token_budget: int,
    strategy: str,
) -> str:
    """Build hybrid metadata response from context tuple."""
    (
        always_loaded_content,
        always_loaded_tokens,
        _,
        _,
        files_map,
        total_tokens_available,
    ) = ctx
    return build_hybrid_metadata_response(
        task_description,
        token_budget,
        strategy,
        files_map,
        total_tokens_available,
        always_loaded_content,
        always_loaded_tokens,
    )


def _finalize_metadata_response(
    ctx: tuple[
        dict[str, str],
        int,
        dict[str, ModelDict],
        dict[str, float],
        list[FileMapEntry],
        int,
    ],
    always_load_sections: dict[str, list[str]],
    task_description: str,
    token_budget: int,
    strategy: str,
    project_root: Path | None,
    agent_role: AgentRole | None,
) -> str:
    """Emit log if needed and build response from context tuple."""
    _emit_metadata_log_if_needed(
        project_root,
        task_description,
        token_budget,
        strategy,
        always_load_sections,
        agent_role,
        ctx,
    )
    return _build_response_from_ctx(ctx, task_description, token_budget, strategy)


async def load_context_metadata_only(
    metadata_index: MetadataIndex,
    task_description: str,
    token_budget: int,
    strategy: str,
    project_root: Path | None,
    optimization_config: OptimizationConfig,
    fs_manager: FileSystemManager,
    agent_role: AgentRole | None = None,
) -> str:
    """Load context map with hybrid retrieval and role-based scoring."""
    always_load_sections = optimization_config.get_always_load_sections()
    ctx = await prepare_hybrid_metadata_context(
        metadata_index, task_description, always_load_sections, fs_manager, agent_role
    )
    return _finalize_metadata_response(
        ctx,
        always_load_sections,
        task_description,
        token_budget,
        strategy,
        project_root,
        agent_role,
    )
