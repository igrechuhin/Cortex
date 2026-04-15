"""Memory bank searcher: BM25 ranked retrieval over .cortex/ markdown files."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.retrieval.bm25 import rank
from cortex.retrieval.chunker import TextChunk, chunk_markdown

_SEARCH_DIRS = (
    CortexResourceType.MEMORY_BANK,
    CortexResourceType.PLANS,
    CortexResourceType.WIKI,
)


class SearchInput(BaseModel):
    """Typed input parameters for a memory bank search request."""

    model_config = ConfigDict(extra="ignore")

    query: str
    top_k: int = 10
    file_filter: list[str] | None = None


class SearchResult(BaseModel):
    """A ranked retrieval result from the memory bank."""

    text: str
    source: str
    score: float
    heading: str
    start_line: int


def deduplicate(results: list[SearchResult]) -> list[SearchResult]:
    """Remove duplicate results by (source, start_line). Preserves order."""
    seen: set[tuple[str, int]] = set()
    unique: list[SearchResult] = []
    for result in results:
        key = (result.source, result.start_line)
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


class MemoryBankSearcher:
    """BM25 ranked search over memory bank, plans, and wiki markdown files."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    def _collect_files(self, file_filter: list[str] | None) -> list[Path]:
        files: list[Path] = []
        for resource_type in _SEARCH_DIRS:
            directory = get_cortex_path(self._root, resource_type)
            if not directory.exists():
                continue
            for path in directory.rglob("*.md"):
                if not path.is_file():
                    continue
                if file_filter is None or path.name in file_filter:
                    files.append(path)
        return files

    def search(
        self,
        query: str,
        top_k: int = 10,
        file_filter: list[str] | None = None,
    ) -> list[SearchResult]:
        """Rank memory bank chunks by BM25 score against query.

        Returns deduplicated SearchResult list sorted by score descending.
        """
        files = self._collect_files(file_filter)
        chunks: list[TextChunk] = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            source = str(path.relative_to(self._root))
            chunks.extend(chunk_markdown(text, source=source))
        if not chunks:
            return []
        ranked = rank(query, [c.text for c in chunks], top_k=top_k)
        results = [
            SearchResult(
                text=chunks[idx].text,
                source=chunks[idx].source,
                score=score,
                heading=chunks[idx].heading,
                start_line=chunks[idx].start_line,
            )
            for idx, score in ranked
        ]
        return deduplicate(results)
