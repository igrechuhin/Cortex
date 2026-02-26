"""
Priority loading helpers for progressive loader.

Extracted from progressive_loader for file size compliance.
"""

from __future__ import annotations

from pathlib import Path

from .progressive_loader_models import LoadedContent
from .progressive_loader_protocols import LoaderProtocol


async def process_priority_file(
    loader: LoaderProtocol,
    file_name: str,
    priority: int,
    priority_order: list[str],
    cumulative_tokens: int,
    token_budget: int,
) -> LoadedContent | None:
    """Process a single file for priority loading."""
    try:
        file_path = resolve_file_path(loader, file_name)
        content, _ = await loader.file_system.read_file(file_path)
        tokens = loader.context_optimizer.token_counter.count_tokens(content)

        if cumulative_tokens + tokens > token_budget:
            return None

        return await build_priority_loaded_content(
            loader,
            file_name,
            content,
            tokens,
            priority,
            priority_order,
            cumulative_tokens,
        )

    except FileNotFoundError:
        return None


async def build_priority_loaded_content(
    loader: LoaderProtocol,
    file_name: str,
    content: str,
    tokens: int,
    priority: int,
    priority_order: list[str],
    cumulative_tokens: int,
) -> LoadedContent:
    """Build LoadedContent for priority file."""
    from .progressive_loader_metadata import build_file_content_metadata

    cumulative_tokens += tokens
    more_available = priority < len(priority_order) - 1
    meta = await loader.metadata_index.get_file_metadata(file_name)
    metadata = build_file_content_metadata(
        meta.model_dump(mode="json") if meta else None,
        tokens=tokens,
        priority=priority,
    )
    return LoadedContent(
        file_name=file_name,
        content=content,
        tokens=tokens,
        cumulative_tokens=cumulative_tokens,
        priority=priority,
        relevance_score=0.0,
        more_available=more_available,
        metadata=metadata,
    )


def resolve_file_path(loader: LoaderProtocol, file_name: str) -> Path:
    """Resolve file path for priority loading."""
    file_path = Path(file_name)
    if not file_path.is_absolute():
        file_path = loader.file_system.memory_bank_dir / file_name
    return file_path
