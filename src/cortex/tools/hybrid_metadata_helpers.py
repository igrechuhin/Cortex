"""
Phase 4: Hybrid Metadata Helpers

Helper functions for hybrid metadata context loading with always-loaded sections.
"""

import logging

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.tools.files.file_section_helpers import extract_content_sections

logger = logging.getLogger(__name__)


async def load_always_load_sections(
    always_load_sections: dict[str, list[str]],
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
) -> dict[str, str]:
    """Load always-load sections in full for hybrid retrieval strategy.

    Args:
        always_load_sections: Dict mapping file names to lists of section headings
        metadata_index: Metadata index manager
        fs_manager: File system manager
        token_counter: Token counter for calculating section tokens

    Returns:
        Dictionary mapping file names to their always-loaded content
        (full file if sections list is empty, or extracted sections)
    """
    always_loaded_content: dict[str, str] = {}

    for file_name, sections in always_load_sections.items():
        file_path = metadata_index.memory_bank_dir / file_name
        if not file_path.exists():
            logger.warning("Always-load file not found: %s", file_name)
            continue

        try:
            content, _ = await fs_manager.read_file(file_path)
            if sections:
                # Extract specific sections
                extracted_content, warning = extract_content_sections(content, sections)
                if warning:
                    logger.warning(
                        "Warning loading sections from %s: %s", file_name, warning
                    )
                always_loaded_content[file_name] = extracted_content
            else:
                # Load entire file
                always_loaded_content[file_name] = content
        except FileNotFoundError:
            logger.warning("Always-load file not found: %s", file_name)
            continue

    return always_loaded_content


def calculate_always_loaded_tokens(
    always_loaded_content: dict[str, str], token_counter: TokenCounter
) -> int:
    """Calculate total tokens for always-loaded content.

    Args:
        always_loaded_content: Dictionary of always-loaded file content
        token_counter: Token counter instance

    Returns:
        Total token count
    """
    return sum(
        token_counter.count_tokens(content)
        for content in always_loaded_content.values()
    )


def filter_metadata_excluding_always_loaded(
    files_metadata: dict[str, ModelDict],
    always_load_sections: dict[str, list[str]],
) -> dict[str, ModelDict]:
    """Filter metadata to exclude always-loaded files.

    Args:
        files_metadata: All file metadata
        always_load_sections: Always-load sections configuration

    Returns:
        Filtered metadata dictionary
    """
    files_to_exclude = set(always_load_sections.keys())
    return {
        name: meta
        for name, meta in files_metadata.items()
        if name not in files_to_exclude
    }
