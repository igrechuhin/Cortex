"""Paragraph-level markdown chunker for BM25 retrieval."""

from pydantic import BaseModel


class TextChunk(BaseModel):
    """A paragraph chunk extracted from a markdown document."""

    text: str
    source: str = ""
    start_line: int
    end_line: int
    heading: str = ""


def _flush_chunk(
    lines: list[str],
    chunks: list[TextChunk],
    source: str,
    start: int,
    end: int,
    heading: str,
) -> None:
    """Append a TextChunk if the paragraph meets the minimum length threshold."""
    para = "\n".join(lines).strip()
    if len(para) >= 20:
        chunks.append(
            TextChunk(
                text=para,
                source=source,
                start_line=start,
                end_line=end,
                heading=heading,
            )
        )
    lines.clear()


def chunk_markdown(text: str, source: str = "") -> list[TextChunk]:
    """Split markdown text into paragraph-level chunks, tracking headings.

    Heading lines (starting with #) update heading context but are excluded
    from chunk content. Minimum chunk size is 20 characters.
    """
    if not text.strip():
        return []
    chunks: list[TextChunk] = []
    heading = ""
    lines: list[str] = []
    start = 1
    last = 0
    for i, line in enumerate(text.splitlines(), 1):
        last = i
        if line.startswith("#"):
            _flush_chunk(lines, chunks, source, start, i - 1, heading)
            heading = line.lstrip("#").strip()
            start = i + 1
        elif not line.strip():
            _flush_chunk(lines, chunks, source, start, i - 1, heading)
            start = i + 1
        else:
            if not lines:
                start = i
            lines.append(line)
    _flush_chunk(lines, chunks, source, start, last, heading)
    return chunks
