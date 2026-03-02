"""
Phase 4: Context loading full/summary content path.

Reads files, loads content, and handles full/summary depth loading.
"""

import logging
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ContextDepth, ModelDict
from cortex.optimization.agent_roles import AgentRole
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_strategies import OptimizationResult
from cortex.tools.context.load_operations_result import (
    format_load_context_result,
    log_context_call,
)
from cortex.tools.context.metadata_helpers import summarize_files_content

logger = logging.getLogger(__name__)


async def read_all_files_for_context_loading(
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
) -> tuple[dict[str, str], dict[str, ModelDict]]:
    """Read all files and their metadata for context loading."""
    all_files = await metadata_index.list_all_files()
    files_content: dict[str, str] = {}
    files_metadata: dict[str, ModelDict] = {}

    for file_name in all_files:
        file_path = metadata_index.memory_bank_dir / file_name
        if not file_path.exists():
            logger.warning("Skipping stale index entry: %s", file_name)
            continue
        try:
            content, _ = await fs_manager.read_file(file_path)
            files_content[file_name] = content

            metadata_raw = await metadata_index.get_file_metadata(file_name)
            if metadata_raw is not None:
                files_metadata[file_name] = metadata_raw.model_dump(
                    mode="json", by_alias=True
                )
        except FileNotFoundError:
            continue

    return files_content, files_metadata


async def load_context_with_content(
    context_optimizer: ContextOptimizer,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: ContextDepth,
) -> OptimizationResult:
    """Load context with file content (summary or full)."""
    files_content, files_metadata = await read_all_files_for_context_loading(
        metadata_index, fs_manager
    )

    if depth == ContextDepth.SUMMARY:
        files_content = summarize_files_content(files_content, files_metadata)

    return await context_optimizer.optimize_context(
        task_description=task_description,
        files_content=files_content,
        files_metadata=files_metadata,
        token_budget=effective_budget,
        strategy=strategy,
    )


async def load_and_format_context_result(
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: ContextDepth,
    result: OptimizationResult,
    project_root: Path | None,
    agent_role: AgentRole | None = None,
) -> str:
    """Load context result and format with logging."""
    if project_root is not None:
        log_context_call(
            project_root,
            task_description,
            effective_budget,
            strategy,
            result,
            agent_role,
        )

    return format_load_context_result(
        task_description, effective_budget, strategy, result, depth=depth
    )


async def handle_full_or_summary_depth(
    context_optimizer: ContextOptimizer,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: ContextDepth,
    project_root: Path | None,
    agent_role: AgentRole | None = None,
) -> str:
    """Handle full or summary depth loading."""
    result = await load_context_with_content(
        context_optimizer,
        metadata_index,
        fs_manager,
        task_description,
        effective_budget,
        strategy,
        depth,
    )
    return await load_and_format_context_result(
        task_description,
        effective_budget,
        strategy,
        depth,
        result,
        project_root,
        agent_role,
    )
