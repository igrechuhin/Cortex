"""
Section parsing, scoring, and selection for summarization engine.

Extracted from summarization_engine for file size compliance.
"""

import re

from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import ParsedSectionModel, ScoredSectionModel
from cortex.optimization.section_scorer import SectionScorer

# AI: name given to content appearing before the first markdown heading.
# Headerless input parses to exactly this one section, which callers must
# treat as "unsectioned" rather than reconstructing under a fake heading.
PREAMBLE_SECTION = "preamble"

# AI: ATX heading only -- 1-6 "#" then required whitespace then text. A bare
# "#" or a "#foo" with no space is ordinary body text, not a heading.
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


def _fence_marker(line: str) -> str | None:
    """Return the fence run (e.g. '```') opening/closing on this line, if any."""
    match = _FENCE_RE.match(line.lstrip())
    return match.group(1) if match else None


def _closes_fence(marker: str, opener: str) -> bool:
    """A fence closes on a same-character run at least as long as the opener."""
    return marker[0] == opener[0] and len(marker) >= len(opener)


def _build_section(
    index: int, name: str, heading_line: str | None, lines: list[str]
) -> ParsedSectionModel:
    """Assemble one section's verbatim source: its heading (if any) plus body."""
    body = "\n".join(lines)
    source = body if heading_line is None else f"{heading_line}\n{body}"
    return ParsedSectionModel(index=index, name=name, source=source)


def _flush_section(
    sections: list[ParsedSectionModel],
    name: str,
    heading_line: str | None,
    lines: list[str],
) -> None:
    """Append the accumulated section, unless it has no body lines at all."""
    if lines:
        sections.append(_build_section(len(sections), name, heading_line, lines))


def _handle_fence_line(
    line: str, fence_opener: str | None, current_lines: list[str]
) -> tuple[bool, str | None]:
    """Absorb a line that opens, continues, or closes a fenced code block.

    Returns ``(absorbed, updated_opener)``; a line inside/opening a fence is
    always body text, so headings are never matched against it.
    """
    marker = _fence_marker(line)
    if fence_opener is not None:
        current_lines.append(line)
        return True, (
            None
            if marker is not None and _closes_fence(marker, fence_opener)
            else fence_opener
        )
    if marker is not None:
        current_lines.append(line)
        return True, marker
    return False, fence_opener


def parse_sections(content: str) -> tuple[list[ParsedSectionModel], bool]:
    """Split markdown into an ordered list of verbatim section slices.

    Each ATX heading (matched only outside fenced code blocks, so a "#"
    comment inside a ``` fence never splits a section) starts a new entry.
    A section's ``source`` is its heading line exactly as written -- at
    whatever level -- plus its body; nothing is re-leveled or rewritten.
    Sections are identified by position, not name, so two identically
    named headings survive as two distinct entries instead of one
    overwriting the other. A heading with no body before the next heading
    (or EOF) contributes nothing, matching headerless-content pass-through.

    Returns ``(sections, has_heading)``. ``has_heading`` records whether an
    ATX heading matched anywhere, independent of section names -- so a
    document whose sole heading is literally named "preamble" is never
    confused with genuinely headerless content by name alone.
    """
    sections: list[ParsedSectionModel] = []
    current_name = PREAMBLE_SECTION
    current_heading: str | None = None
    current_lines: list[str] = []
    fence_opener: str | None = None
    has_heading = False

    for line in content.split("\n"):
        absorbed, fence_opener = _handle_fence_line(line, fence_opener, current_lines)
        if absorbed:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match is None:
            current_lines.append(line)
            continue

        has_heading = True
        _flush_section(sections, current_name, current_heading, current_lines)
        current_name = heading_match.group(1).strip()
        current_heading = line
        current_lines = []

    _flush_section(sections, current_name, current_heading, current_lines)
    return sections, has_heading


def passthrough_unsectioned(content: str) -> str:
    """Return content unchanged when it has no parseable sections.

    # AI: this previously truncated to 50% of the words and appended a
    # "[Content truncated...]" marker, silently destroying paths, errors,
    # and constraints in unsectioned content. There is nothing to trim by
    # section here, so this is a pass-through; a resulting zero reduction
    # is surfaced by the caller's target-compliance check rather than
    # hidden behind a fake truncation.
    """
    return content


def score_all_sections(
    sections: list[ParsedSectionModel],
    token_counter: TokenCounter,
    scorer: SectionScorer,
) -> list[ScoredSectionModel]:
    """Score all sections by importance using the injected scorer."""
    section_scores: list[ScoredSectionModel] = []

    for section in sections:
        score = scorer.score(section.name, section.source)
        tokens = token_counter.count_tokens(section.source)

        section_scores.append(
            ScoredSectionModel(
                index=section.index,
                name=section.name,
                source=section.source,
                score=score,
                tokens=tokens,
            )
        )

    return section_scores


def select_sections_by_budget(
    section_scores: list[ScoredSectionModel], target_tokens: int
) -> tuple[list[ScoredSectionModel], list[ScoredSectionModel]]:
    """Select sections within token budget.

    Returns ``(selected, dropped)``. Every section that does not make the
    cut is reported in ``dropped`` (with its score and token count intact)
    so callers can attach drop provenance to the result.
    """
    selected: list[ScoredSectionModel] = []
    dropped: list[ScoredSectionModel] = []
    total_tokens = 0
    forced_only_section = False

    for section in section_scores:
        if forced_only_section:
            dropped.append(section)
        elif total_tokens + section.tokens <= target_tokens:
            selected.append(section)
            total_tokens += section.tokens
        elif not selected:
            # Include at least one section even if it exceeds budget
            selected.append(section)
            forced_only_section = True
        else:
            dropped.append(section)

    if dropped and _note_cost(len(dropped)) >= _source_chars(dropped):
        # AI: the note would cost at least as much as the text it stands in
        # for, so the drop buys nothing and only loses content. Keeping the
        # sections is strictly the smaller output, and leaves `dropped`
        # truthful: nothing is reported dropped that still appears.
        selected.extend(dropped)
        dropped = []

    return selected, dropped


def _source_chars(sections: list[ScoredSectionModel]) -> int:
    """Characters of original source the given sections occupy."""
    return sum(len(section.source) for section in sections)


def _bare_note(count: int) -> str:
    """Smallest note that still discloses the omission."""
    return f"[{count} section{'s' if count != 1 else ''} omitted]"


def _note_cost(count: int) -> int:
    """Cost of the smallest note, including the newline joining it on."""
    return len(_bare_note(count)) + 1


def _omission_note(dropped_sections: list[ScoredSectionModel]) -> str:
    """Build the note disclosing dropped sections, bounded by what it saves.

    Naming every section is the useful form, but a run of tiny sections with
    long headings can produce a note as large as the text it replaces -- the
    caller pays a reduction of roughly zero and still loses the content. When
    the named form is not strictly smaller than the source it stands in for,
    it degrades to the count alone, which still discloses the omission.

    The bare form is not bounded here: `select_sections_by_budget` refuses a
    drop the bare note cannot pay for, so by the time a note is built the
    sections are known to cost more than disclosing them.
    """
    named = (
        f"[{len(dropped_sections)} sections omitted: "
        f"{', '.join(section.name for section in dropped_sections)}]"
    )
    if len(named) + 1 < _source_chars(dropped_sections):
        return named
    return _bare_note(len(dropped_sections))


def reconstruct_content(
    selected_sections: list[ScoredSectionModel],
    dropped_sections: list[ScoredSectionModel],
) -> str:
    """Reconstruct content by replaying kept sections verbatim.

    Never synthesizes a heading: each kept section's original source slice
    (its heading line as written, at whatever level, plus body) is replayed
    unchanged. Only the omission note naming what was dropped is generated.
    """
    parts = [section.source for section in selected_sections]

    if dropped_sections:
        parts.append(_omission_note(dropped_sections))

    return "\n".join(parts)
