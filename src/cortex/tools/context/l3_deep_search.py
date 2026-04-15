"""L3 deep search context layer builder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.retrieval.bm25 import rank
from cortex.tools.context.layers import ContextLayer, LayerResult


@dataclass(frozen=True)
class _ParagraphMatch:
    score: float
    source: str
    start_line: int
    end_line: int
    text: str


def _iter_markdown_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for resource in (
        CortexResourceType.MEMORY_BANK,
        CortexResourceType.PLANS,
        CortexResourceType.WIKI,
    ):
        base = get_cortex_path(project_root, resource)
        if base.is_dir():
            files.extend(sorted(base.glob("*.md")))
    return files


def _split_paragraphs_with_lines(content: str) -> list[tuple[int, int, str]]:
    lines = content.splitlines()
    blocks: list[tuple[int, int, str]] = []
    start = 0
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            if start < idx - 1:
                text = "\n".join(lines[start : idx - 1]).strip()
                if text:
                    blocks.append((start + 1, idx - 1, text))
            start = idx
    if start < len(lines):
        text = "\n".join(lines[start:]).strip()
        if text:
            blocks.append((start + 1, len(lines), text))
    return blocks


def _collect_ranked_matches(project_root: Path, query: str) -> list[_ParagraphMatch]:
    all_paragraphs: list[tuple[str, int, int, str]] = []  # (source, start, end, text)
    for path in _iter_markdown_files(project_root):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        source = str(path.relative_to(project_root))
        for start_line, end_line, paragraph in _split_paragraphs_with_lines(content):
            all_paragraphs.append((source, start_line, end_line, paragraph))
    if not all_paragraphs:
        return []
    ranked = rank(query, [p[3] for p in all_paragraphs])
    return [
        _ParagraphMatch(
            score=score,
            source=all_paragraphs[idx][0],
            start_line=all_paragraphs[idx][1],
            end_line=all_paragraphs[idx][2],
            text=all_paragraphs[idx][3],
        )
        for idx, score in ranked
    ]


async def build_l3(project_root: Path, query: str) -> LayerResult:
    top_matches = _collect_ranked_matches(project_root, query)[:10]
    content = "\n\n".join(
        (
            f"[{item.source}:{item.start_line}-{item.end_line}] "
            f"(score={item.score:.3f})\n{item.text}"
        )
        for item in top_matches
    )
    return LayerResult(
        layer=ContextLayer.DEEP_SEARCH,
        tokens_estimate=len(content.split()),
        content=content,
        sources=[match.source for match in top_matches],
    )
