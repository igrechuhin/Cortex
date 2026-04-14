"""L2 on-demand context layer builder."""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.context.layers import ContextConfig, ContextLayer, LayerResult


def _count_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _truncate_paragraphs(content: str, max_tokens: int) -> str:
    paragraphs = [
        segment.strip() for segment in content.split("\n\n") if segment.strip()
    ]
    selected: list[str] = []
    for paragraph in paragraphs:
        candidate = "\n\n".join(selected + [paragraph]).strip()
        if _count_tokens(candidate) > max_tokens:
            break
        selected.append(paragraph)
    return "\n\n".join(selected).strip()


def _resolve_topic_path(project_root: Path, topic: str) -> Path | None:
    topic_name = f"{topic}.md"
    exact_candidates = [
        get_cortex_path(project_root, CortexResourceType.PLANS) / topic_name,
        get_cortex_path(project_root, CortexResourceType.MEMORY_BANK) / topic_name,
        get_cortex_path(project_root, CortexResourceType.WIKI) / topic_name,
    ]
    for path in exact_candidates:
        if path.is_file():
            return path
    topic_word = topic.lower().split("-", 1)[0]
    for resource in (
        CortexResourceType.PLANS,
        CortexResourceType.MEMORY_BANK,
        CortexResourceType.WIKI,
    ):
        directory = get_cortex_path(project_root, resource)
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.stem.lower().startswith(topic_word):
                return path
    return None


async def build_l2(
    project_root: Path, config: ContextConfig, topic: str
) -> LayerResult:
    resolved = _resolve_topic_path(project_root, topic)
    if resolved is None:
        return LayerResult(
            layer=ContextLayer.ON_DEMAND,
            tokens_estimate=0,
            content="",
            sources=[],
        )
    try:
        content = resolved.read_text(encoding="utf-8")
    except OSError:
        content = ""
    truncated = _truncate_paragraphs(content, config.max_l2_tokens)
    return LayerResult(
        layer=ContextLayer.ON_DEMAND,
        tokens_estimate=_count_tokens(truncated),
        content=truncated,
        sources=[str(resolved.relative_to(project_root))],
    )
