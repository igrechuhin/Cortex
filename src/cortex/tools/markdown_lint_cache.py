"""
Markdown lint cache: index type and load/save helpers.

Extracted from markdown_operations to keep main module under 400 lines.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.context_logging import MCPContext, log_client

_MARKDOWN_LINT_CACHE_KEY = "markdown-lint-index.json"


class MarkdownLintIndex(BaseModel):
    """On-disk index for markdown lint cache: path -> content hash (clean files only)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: str = Field(default="2.0", description="Schema version")
    files: dict[str, str] = Field(
        default_factory=dict,
        description="Map of relative path to sha256 content hash (clean only)",
    )


async def load_markdown_lint_index(project_root: Path) -> MarkdownLintIndex:
    """Load markdown lint index from .cortex/.cache/markdown-lint-index.json (concurrent-safe).

    Accepts only v2 format (version "2.0", files = { path: "sha256:..." }).
    Missing file or any other format returns empty index; next run will rescan.
    """
    raw = await read_cache_json(project_root, _MARKDOWN_LINT_CACHE_KEY)
    if raw is None or not isinstance(raw, dict):
        return MarkdownLintIndex()
    try:
        return MarkdownLintIndex.model_validate(raw)
    except Exception:
        return MarkdownLintIndex()


async def save_markdown_lint_index(
    project_root: Path, index: MarkdownLintIndex
) -> None:
    """Persist markdown lint index to .cortex/.cache/markdown-lint-index.json (concurrent-safe).

    Uses cache_json_access.write_cache_json. fix_markdown_lint updates this automatically.

    Catches exceptions (e.g., FileLockTimeoutError) to prevent server crashes.
    Cache write failures are non-fatal - lint results are still returned.
    """
    try:
        await write_cache_json(
            project_root, _MARKDOWN_LINT_CACHE_KEY, index.model_dump(), indent=2
        )
    except Exception as e:
        await log_client(
            None,
            "warning",
            f"Failed to save markdown lint cache: {e}",
            logger_name=__name__,
        )


async def load_markdown_lint_index_safe(
    root_path: Path, ctx: MCPContext | None = None
) -> MarkdownLintIndex:
    """Load markdown lint index with error handling. Returns empty index if load fails (non-fatal)."""
    try:
        return await load_markdown_lint_index(root_path)
    except Exception as e:
        await log_client(
            ctx,
            "warning",
            f"Failed to load markdown lint cache: {e}, using empty index",
            logger_name=__name__,
        )
        return MarkdownLintIndex()
