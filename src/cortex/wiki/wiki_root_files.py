"""Normative wiki-root filenames under ``.cortex/wiki/``."""

from __future__ import annotations

from enum import Enum


class WikiRootDocument(str, Enum):
    """Fixed markdown files at the wiki root (not category subfolders)."""

    SCHEMA = "schema.md"
    INDEX = "index.md"


# Relative paths (posix filenames) excluded from index-catalog / staleness checks.
WIKI_ROOT_DOCUMENT_NAMES: frozenset[str] = frozenset(d.value for d in WikiRootDocument)
