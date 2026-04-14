"""L1 essential story layer builder."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.memory.memory_types import MemoryType
from cortex.tools.context.layers import ContextConfig, ContextLayer, LayerResult

_KEYWORDS = ("blocker", "active", "decision", "pending")
_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_TYPE_RE = re.compile(r"<!--\s*memory_type:\s*([a-z_]+)\s*-->", re.IGNORECASE)
_TYPE_WEIGHTS = {
    MemoryType.DECISION: 3.0,
    MemoryType.PREFERENCE: 2.5,
    MemoryType.PROBLEM: 2.0,
    MemoryType.MILESTONE: 1.5,
    MemoryType.STATUS: 0.0,
}


@dataclass(frozen=True)
class _ScoredParagraph:
    text: str
    score: float
    source: str


def _count_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _extract_paragraphs(content: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", content) if chunk.strip()]


def score_paragraph(paragraph: str) -> float:
    lowered = paragraph.lower()
    keyword_score = sum(lowered.count(keyword) for keyword in _KEYWORDS) * 2.0
    recency_score = 3.0 if _DATE_RE.search(paragraph) else 0.0
    heading_bonus = 1.5 if paragraph.startswith("#") else 0.0
    return (
        keyword_score + recency_score + heading_bonus + _memory_type_weight(paragraph)
    )


def _memory_type_weight(paragraph: str) -> float:
    match = _TYPE_RE.search(paragraph)
    if match is None:
        return 0.0
    try:
        memory_type = MemoryType(match.group(1).lower())
    except ValueError:
        return 0.0
    return _TYPE_WEIGHTS[memory_type]


def _select_scored_paragraphs(
    scored: list[_ScoredParagraph], config: ContextConfig
) -> list[_ScoredParagraph]:
    selected: list[_ScoredParagraph] = []
    for paragraph in scored[: max(config.l1_source_limit * 8, 1)]:
        candidate = _build_summary_content(selected + [paragraph], 0)
        if _count_tokens(candidate) > config.max_l1_tokens:
            continue
        selected.append(paragraph)
        if len(selected) >= config.l1_source_limit:
            break
    return selected


def _build_summary_content(selected: list[_ScoredParagraph], omitted_count: int) -> str:
    lines = ["Essential story"]
    for idx, entry in enumerate(selected, start=1):
        lines.append(f"Entry {idx} ({entry.source})")
        lines.append(entry.text)
    lines.append(f"[{omitted_count} more entries available in L2/L3]")
    return "\n\n".join(lines).strip()


async def build_l1(project_root: Path, config: ContextConfig) -> LayerResult:
    memory_bank = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    scored: list[_ScoredParagraph] = []
    for name in ("activeContext.md", "progress.md"):
        path = memory_bank / name
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for paragraph in _extract_paragraphs(content):
            scored.append(_ScoredParagraph(paragraph, score_paragraph(paragraph), name))
    scored.sort(key=lambda item: item.score, reverse=True)
    selected = _select_scored_paragraphs(scored, config)
    content = _build_summary_content(selected, max(len(scored) - len(selected), 0))
    return LayerResult(
        layer=ContextLayer.ESSENTIAL,
        tokens_estimate=_count_tokens(content),
        content=content,
        sources=sorted({item.source for item in selected}),
    )
