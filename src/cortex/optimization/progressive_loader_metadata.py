"""
Metadata building utilities for progressive loading.

Extracted from progressive_loader for file size compliance.
"""

from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.optimization.models import FileContentMetadata


def build_file_content_metadata(
    metadata: ModelDict | None,
    *,
    tokens: int | None,
    priority: int | None,
) -> FileContentMetadata:
    """Build FileContentMetadata from dict-shaped metadata index entry."""
    meta: dict[str, JsonValue] = metadata if isinstance(metadata, dict) else {}

    sections_raw = meta.get("sections", [])
    section_headings: list[str] = []
    if isinstance(sections_raw, list):
        for item in cast(list[JsonValue], sections_raw):
            if isinstance(item, str):
                section_headings.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_dict = cast(dict[str, JsonValue], item)
            heading = item_dict.get("heading")
            if isinstance(heading, str) and heading:
                section_headings.append(heading)

    sections_json = cast(list[JsonValue], section_headings)
    out: dict[str, JsonValue] = {
        "content_hash": meta.get("content_hash"),
        "last_modified": meta.get("last_modified"),
        "sections": sections_json,
        "tokens": tokens,
        "priority": priority,
    }
    return FileContentMetadata.model_validate(out)
