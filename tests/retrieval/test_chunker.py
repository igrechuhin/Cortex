"""Unit tests for cortex.retrieval.chunker."""

from cortex.retrieval.chunker import TextChunk, chunk_markdown


class TestChunkMarkdown:
    def test_empty_string_returns_empty(self) -> None:
        assert chunk_markdown("") == []

    def test_whitespace_only_returns_empty(self) -> None:
        assert chunk_markdown("   \n  \n") == []

    def test_single_paragraph(self) -> None:
        text = "This is a single paragraph with enough content to exceed minimum."
        chunks = chunk_markdown(text)
        assert len(chunks) == 1
        assert "single paragraph" in chunks[0].text

    def test_three_paragraphs_under_two_headings(self) -> None:
        text = (
            "# Heading One\n"
            "\n"
            "Paragraph one content that is long enough to qualify as a chunk.\n"
            "\n"
            "## Heading Two\n"
            "\n"
            "Paragraph two content that is also long enough for our purposes.\n"
            "\n"
            "Paragraph three under heading two with sufficient text content.\n"
        )
        chunks = chunk_markdown(text)
        assert len(chunks) == 3
        assert chunks[0].heading == "Heading One"
        assert chunks[1].heading == "Heading Two"
        assert chunks[2].heading == "Heading Two"

    def test_heading_not_included_in_chunk_text(self) -> None:
        text = "# My Heading\n\nSome content below the heading that qualifies.\n"
        chunks = chunk_markdown(text)
        assert all("#" not in c.text for c in chunks)

    def test_minimum_chunk_size_filter(self) -> None:
        text = (
            "# Header\n\nshort\n\nThis paragraph is definitely long enough to pass.\n"
        )
        chunks = chunk_markdown(text)
        texts = [c.text for c in chunks]
        assert not any(len(t) < 20 for t in texts)
        assert any("long enough" in t for t in texts)

    def test_source_propagated(self) -> None:
        text = "First paragraph content that is long enough to qualify here.\n"
        chunks = chunk_markdown(text, source="activeContext.md")
        assert all(c.source == "activeContext.md" for c in chunks)

    def test_start_end_line_tracking(self) -> None:
        text = "Line one of content\nLine two of content\nLine three of content\n"
        chunks = chunk_markdown(text)
        assert len(chunks) == 1
        assert chunks[0].start_line == 1
        assert chunks[0].end_line >= 3

    def test_multiple_blank_lines_no_duplicate_chunks(self) -> None:
        text = "First paragraph here with enough content.\n\n\n\nSecond paragraph here too.\n"
        chunks = chunk_markdown(text)
        assert len(chunks) == 2

    def test_no_heading_gives_empty_heading(self) -> None:
        text = "Content without any heading, but long enough to qualify as a chunk."
        chunks = chunk_markdown(text)
        assert len(chunks) == 1
        assert chunks[0].heading == ""

    def test_text_chunk_is_pydantic_model(self) -> None:
        chunk = TextChunk(text="hello world", start_line=1, end_line=1)
        assert chunk.text == "hello world"
        assert chunk.heading == ""
        assert chunk.source == ""
