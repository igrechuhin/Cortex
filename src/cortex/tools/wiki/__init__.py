"""Wiki tooling for pipelines (auto-ingest, staged doc processing)."""

from __future__ import annotations

from cortex.tools.wiki.auto_ingest_config import (
    DEFAULT_AUTO_INGEST_PATTERNS,
    load_auto_ingest_patterns,
)
from cortex.tools.wiki.staged_ingest import (
    WikiStagedIngestResult,
    wiki_ingest_staged_docs,
)

__all__ = [
    "DEFAULT_AUTO_INGEST_PATTERNS",
    "WikiStagedIngestResult",
    "load_auto_ingest_patterns",
    "wiki_ingest_staged_docs",
]
