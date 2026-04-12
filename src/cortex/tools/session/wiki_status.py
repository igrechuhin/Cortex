"""Wiki orientation fields for session_start (project-wiki plan Step 2)."""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import (
    WIKI_DIR_PROJECT_RELATIVE_POSIX,
    CortexResourceType,
    get_cortex_path,
)
from cortex.tools.session.models import WikiStatusSummary

_DOC_NAMES: frozenset[str] = frozenset(
    {"README.md", "Readme.md", "readme.md", "CHANGELOG.md", "CONTRIBUTING.md"}
)


def project_has_wiki_seed_docs(project_root: Path) -> bool:
    """Return True when the repo has obvious doc seeds for `/cortex/init-wiki`."""
    for name in _DOC_NAMES:
        if (project_root / name).is_file():
            return True
    docs = project_root / "docs"
    if not docs.is_dir():
        return False
    for child in docs.iterdir():
        if child.is_file() and child.suffix.lower() == ".md":
            return True
    adr = docs / "adr"
    if adr.is_dir():
        for child in adr.glob("*.md"):
            if child.is_file():
                return True
    return False


def compute_wiki_status(project_root: Path) -> WikiStatusSummary:
    """Derive wiki_enabled, page count, and canonical wiki path for session briefs."""
    cortex_dir = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
    if not cortex_dir.is_dir():
        return WikiStatusSummary()
    wiki_rel = WIKI_DIR_PROJECT_RELATIVE_POSIX
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    if not wiki_root.is_dir():
        return WikiStatusSummary(
            wiki_enabled=False, wiki_page_count=0, wiki_path=wiki_rel
        )
    cap = 5000
    count = 0
    for _ in wiki_root.rglob("*.md"):
        count += 1
        if count >= cap:
            break
    return WikiStatusSummary(
        wiki_enabled=True, wiki_page_count=count, wiki_path=wiki_rel
    )


def append_session_wiki_init_hint(
    suggestions: list[str],
    wiki_status: WikiStatusSummary | None,
    project_root: Path | None,
) -> None:
    # AI: Non-blocking orientation only; avoids nagging when no seed docs exist to ingest.
    if wiki_status is None or project_root is None:
        return
    if not get_cortex_path(project_root, CortexResourceType.CORTEX_DIR).is_dir():
        return
    if wiki_status.wiki_enabled:
        return
    if project_has_wiki_seed_docs(project_root):
        suggestions.append(
            "Wiki not found. Run `/cortex/init-wiki` to seed it from existing docs."
        )
