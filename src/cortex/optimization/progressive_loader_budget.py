"""
Budget-based file loading helpers for progressive loader.

Extracted from progressive_loader for file size compliance.
"""

from pathlib import Path

from .progressive_loader_metadata import build_file_content_metadata
from .progressive_loader_models import LoadedContent, LoadedFileContent
from .progressive_loader_protocols import LoaderProtocol


def to_loaded_content(
    file_name: str,
    content_item: LoadedFileContent,
    priority: int,
    more_available: bool,
) -> LoadedContent:
    """Build LoadedContent from LoadedFileContent."""
    return LoadedContent(
        file_name=file_name,
        content=content_item.content,
        tokens=content_item.tokens,
        cumulative_tokens=content_item.cumulative_tokens,
        priority=priority,
        relevance_score=0.0,
        more_available=more_available,
        metadata=content_item.metadata,
    )


async def load_file_with_budget_check(
    loader: LoaderProtocol,
    file_name: str,
    cumulative_tokens: int,
    token_budget: int,
    *,
    stop_at_budget: bool = True,
) -> LoadedFileContent | None:
    """Load a single file and check budget constraints."""
    try:
        file_path = Path(file_name)
        if not file_path.is_absolute():
            file_path = loader.file_system.memory_bank_dir / file_name
        content, _ = await loader.file_system.read_file(file_path)

        tokens = loader.context_optimizer.token_counter.count_tokens(content)

        if stop_at_budget and cumulative_tokens + tokens > token_budget:
            return None

        meta = await loader.metadata_index.get_file_metadata(file_name)
        metadata = build_file_content_metadata(
            meta.model_dump(mode="json") if meta else None,
            tokens=tokens,
            priority=None,
        )

        return LoadedFileContent(
            content=content,
            tokens=tokens,
            cumulative_tokens=cumulative_tokens + tokens,
            metadata=metadata,
        )
    except FileNotFoundError:
        return None
