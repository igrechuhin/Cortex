"""Canonical wiki category directory names (on-disk under ``.cortex/wiki/``)."""

from __future__ import annotations

from enum import Enum


class WikiCategoryDir(str, Enum):
    """Wiki content category folder names; values are directory segments."""

    CONCEPTS = "concepts"
    ENTITIES = "entities"
    DECISIONS = "decisions"
    WORKFLOWS = "workflows"
    SOURCES = "sources"
    ANALYSES = "analyses"


# Order for layout bootstrap and ``expected_wiki_category_dirs`` (stable public contract).
WIKI_CATEGORY_DIR_ORDER: tuple[WikiCategoryDir, ...] = (
    WikiCategoryDir.CONCEPTS,
    WikiCategoryDir.ENTITIES,
    WikiCategoryDir.DECISIONS,
    WikiCategoryDir.WORKFLOWS,
    WikiCategoryDir.SOURCES,
    WikiCategoryDir.ANALYSES,
)

# AI: Ingest summary pages never use ``sources/`` (immutable raw only); tags pick among these.
WIKI_INGEST_SUMMARY_CATEGORY_DIRS: frozenset[WikiCategoryDir] = frozenset(
    {
        WikiCategoryDir.CONCEPTS,
        WikiCategoryDir.ENTITIES,
        WikiCategoryDir.DECISIONS,
        WikiCategoryDir.WORKFLOWS,
        WikiCategoryDir.ANALYSES,
    }
)
