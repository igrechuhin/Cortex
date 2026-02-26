"""
Relevance loading helpers for progressive loader.

Extracted from progressive_loader for file size compliance.
"""

from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import FileContentMetadata, FileMetadataForScoring
from cortex.optimization.optimization_strategies import OptimizationResult

from .context_optimizer import ContextOptimizer
from .progressive_loader_models import LoadedContent


async def optimize_and_build_loaded_content(
    context_optimizer: ContextOptimizer,
    task_description: str,
    files_content: dict[str, str],
    files_metadata: dict[str, FileMetadataForScoring],
    token_budget: int,
    quality_scores: dict[str, float] | None,
) -> list[LoadedContent]:
    """Optimize context and build LoadedContent objects."""
    files_metadata_for_optimizer: dict[str, ModelDict] = {
        file_name: cast(ModelDict, meta.model_dump(mode="json"))
        for file_name, meta in files_metadata.items()
    }
    optimization_result = await context_optimizer.optimize_context(
        task_description=task_description,
        files_content=files_content,
        files_metadata=files_metadata_for_optimizer,
        token_budget=token_budget,
        strategy="priority",
        quality_scores=quality_scores,
    )

    relevance_scores = extract_relevance_scores_from_metadata(
        optimization_result.metadata
    )

    return build_loaded_content_from_optimization(
        optimization_result,
        files_content,
        files_metadata,
        relevance_scores,
        context_optimizer.token_counter,
    )


async def read_all_files_for_loading(
    metadata_index: MetadataIndex,
    file_system: FileSystemManager,
) -> tuple[dict[str, str], dict[str, FileMetadataForScoring]]:
    """Read all files for loading."""
    all_files = await metadata_index.list_all_files()
    files_content: dict[str, str] = {}
    files_metadata: dict[str, FileMetadataForScoring] = {}

    for file_name in all_files:
        file_path = Path(metadata_index.memory_bank_dir) / file_name
        if not file_path.exists():
            continue
        try:
            content, _ = await file_system.read_file(file_path)
            files_content[file_name] = content

            metadata = await metadata_index.get_file_metadata(file_name)
            if metadata is not None:
                files_metadata[file_name] = FileMetadataForScoring.model_validate(
                    metadata.model_dump(mode="json")
                )

        except FileNotFoundError:
            continue

    return files_content, files_metadata


def extract_relevance_scores_from_metadata(
    metadata: dict[str, JsonValue] | None,
) -> dict[str, float]:
    """Extract relevance scores from optimization result metadata."""
    relevance_scores: dict[str, float] = {}
    if not metadata:
        return relevance_scores

    raw = metadata.get("relevance_scores")
    if isinstance(raw, dict):
        raw_dict = cast(dict[str, JsonValue], raw)
        for key, value_raw in raw_dict.items():
            if isinstance(value_raw, (int, float)):
                relevance_scores[str(key)] = float(value_raw)

    return relevance_scores


def build_loaded_content_from_optimization(
    optimization_result: OptimizationResult,
    files_content: dict[str, str],
    files_metadata: dict[str, FileMetadataForScoring],
    relevance_scores: dict[str, float],
    token_counter: TokenCounter,
) -> list[LoadedContent]:
    """Build LoadedContent objects from optimization result."""
    loaded_content: list[LoadedContent] = []
    cumulative_tokens = 0

    for priority, file_name in enumerate(optimization_result.selected_files):
        content_item = build_single_loaded_content(
            file_name,
            files_content,
            files_metadata,
            relevance_scores,
            token_counter,
            priority,
            cumulative_tokens,
        )
        loaded_content.append(content_item)
        cumulative_tokens += content_item.tokens

    return loaded_content


def build_single_loaded_content(
    file_name: str,
    files_content: dict[str, str],
    files_metadata: dict[str, FileMetadataForScoring],
    relevance_scores: dict[str, float],
    token_counter: TokenCounter,
    priority: int,
    cumulative_tokens: int,
) -> LoadedContent:
    """Build a single LoadedContent object."""
    content = files_content[file_name]
    tokens = token_counter.count_tokens(content)
    relevance_score = relevance_scores.get(file_name, 0.0)
    file_metadata = files_metadata.get(file_name)
    meta_dict: dict[str, JsonValue] = (
        file_metadata.model_dump(mode="json") if file_metadata is not None else {}
    )
    meta_dict["tokens"] = tokens
    meta_dict["priority"] = priority
    metadata_model = FileContentMetadata.model_validate(meta_dict)
    return LoadedContent(
        file_name=file_name,
        content=content,
        tokens=tokens,
        cumulative_tokens=cumulative_tokens + tokens,
        priority=priority,
        relevance_score=relevance_score,
        more_available=True,
        metadata=metadata_model,
    )
