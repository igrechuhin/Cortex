"""
Content compression and header extraction for summarization engine.

Extracted from summarization_engine for file size compliance.
"""

import re

from cortex.optimization.models import SummarizationState


def compress_verbose_content(content: str) -> str:
    """
    Remove verbose examples and compress repeated info.

    Args:
        content: Full content

    Returns:
        Compressed content
    """
    lines = content.split("\n")
    result_lines: list[str] = []
    state = SummarizationState()

    for line in lines:
        processed = _process_code_block(line, state, result_lines)
        if processed:
            continue

        processed = _process_example_section(line, state, result_lines)
        if processed:
            continue

        _process_line(line, result_lines)

    return "\n".join(result_lines)


def extract_headers_only(content: str) -> str:
    """
    Extract only headers and first paragraph of each section.

    Args:
        content: Full content

    Returns:
        Headers and brief descriptions
    """
    lines = content.split("\n")
    result_lines: list[str] = []

    current_section_lines: list[str] = []
    in_section = False

    for line in lines:
        if line.startswith("#"):
            _finalize_previous_section(in_section, current_section_lines, result_lines)
            result_lines.append(line)
            current_section_lines = []
            in_section = True
        elif in_section and line.strip():
            current_section_lines.append(line)

    _finalize_previous_section(True, current_section_lines, result_lines)

    return "\n".join(result_lines)


def _finalize_previous_section(
    in_section: bool,
    current_section_lines: list[str],
    result_lines: list[str],
) -> None:
    """Finalize and save previous section if it exists."""
    if not in_section or not current_section_lines:
        return

    result_lines.extend(current_section_lines[:5])
    if len(current_section_lines) > 5:
        result_lines.append("[...]")
    result_lines.append("")


def _process_code_block(
    line: str, state: SummarizationState, result_lines: list[str]
) -> bool:
    """Process code block line."""
    if line.strip().startswith("```"):
        if not state.in_code_block:
            state.in_code_block = True
            state.code_block_lines = [line]
        else:
            state.in_code_block = False
            state.code_block_lines.append(line)

            if len(state.code_block_lines) > 20:
                result_lines.append(state.code_block_lines[0])
                result_lines.append("# ... code omitted ...")
                result_lines.append(state.code_block_lines[-1])
            else:
                result_lines.extend(state.code_block_lines)

            state.code_block_lines = []
        return True

    if state.in_code_block:
        state.code_block_lines.append(line)
        return True

    return False


def _process_example_section(
    line: str, state: SummarizationState, result_lines: list[str]
) -> bool:
    """Process example section line."""
    if re.match(r"^#+\s+Example", line, re.IGNORECASE):
        state.in_example = True
        result_lines.append(line)
        result_lines.append("[Example omitted]")
        return True

    if state.in_example and line.startswith("#"):
        state.in_example = False
        result_lines.append(line)
        return True

    if state.in_example:
        return True

    return False


def _process_line(line: str, result_lines: list[str]) -> None:
    """Process regular line."""
    if len(line) > 500:
        result_lines.append(line[:200] + " ... [truncated]")
    else:
        result_lines.append(line)
