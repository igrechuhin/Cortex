"""Auto-ingest glob patterns for wiki updates during the commit pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

DEFAULT_AUTO_INGEST_PATTERNS: list[str] = [
    "README*.md",
    "docs/**/*.md",
    "adr-*.md",
    "ADR-*.md",
    "CHANGELOG.md",
    "ARCHITECTURE.md",
    "*.design.md",
]


def _extract_leading_yaml_frontmatter(text: str) -> dict[str, object] | None:
    """Return parsed mapping from an optional leading ``---`` YAML block, else None."""
    if not text.startswith("---"):
        return None
    rest = text[3:].lstrip("\n")
    close = rest.find("\n---")
    if close == -1:
        return None
    yaml_block = rest[:close].strip()
    if not yaml_block:
        return None
    parsed: object = yaml.safe_load(yaml_block)
    if not isinstance(parsed, dict):
        return None
    return cast(dict[str, object], parsed)


def load_auto_ingest_patterns(project_root: Path) -> list[str]:
    """Load patterns from ``.cortex/wiki/schema.md`` frontmatter when present; else defaults."""
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    schema_path = wiki_root / "schema.md"
    if not schema_path.is_file():
        return list(DEFAULT_AUTO_INGEST_PATTERNS)
    raw = schema_path.read_text(encoding="utf-8")
    fm = _extract_leading_yaml_frontmatter(raw)
    if fm is None:
        return list(DEFAULT_AUTO_INGEST_PATTERNS)
    raw_patterns = fm.get("auto_ingest_patterns")
    if not isinstance(raw_patterns, list):
        return list(DEFAULT_AUTO_INGEST_PATTERNS)
    out: list[str] = []
    for item in cast(list[object], raw_patterns):
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out if out else list(DEFAULT_AUTO_INGEST_PATTERNS)


def paths_matching_patterns(project_root: Path, patterns: list[str]) -> set[str]:
    """Project-root-relative posix paths of files matching any pattern."""
    matched: set[str] = set()
    for pattern in patterns:
        for path in project_root.glob(pattern):
            try:
                if path.is_file():
                    matched.add(path.relative_to(project_root).as_posix())
            except ValueError:
                continue
    return matched
