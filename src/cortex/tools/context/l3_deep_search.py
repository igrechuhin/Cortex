"""L3 deep search context layer builder."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.context.layers import ContextLayer, LayerResult


@dataclass(frozen=True)
class _ParagraphMatch:
    score: float
    source: str
    start_line: int
    end_line: int
    text: str


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _bm25_score(query: str, text: str) -> float:
    q_tokens = _tokenize(query)
    d_tokens = _tokenize(text)
    if not q_tokens or not d_tokens:
        return 0.0
    counts = Counter(d_tokens)
    total = 0.0
    for token in q_tokens:
        term = counts.get(token, 0)
        if term == 0:
            continue
        total += ((term * 2.2) / (term + 1.2)) * (1.0 + math.log(1 + term))
    return total


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
    matches: list[_ParagraphMatch] = []
    for path in _iter_markdown_files(project_root):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for start_line, end_line, paragraph in _split_paragraphs_with_lines(content):
            score = _bm25_score(query, paragraph)
            if score > 0:
                matches.append(
                    _ParagraphMatch(
                        score=score,
                        source=str(path.relative_to(project_root)),
                        start_line=start_line,
                        end_line=end_line,
                        text=paragraph,
                    )
                )
    matches.sort(key=lambda item: (-item.score, item.source, item.start_line))
    return matches


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
