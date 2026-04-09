"""Prompt builders for Cortex file compression."""

from __future__ import annotations


def build_compress_prompt(original: str) -> str:
    """Build the base prompt used for first-pass compression."""

    return (
        "Compress the following Markdown technical documentation.\n"
        "Drop articles, filler phrases, hedging, pleasantries, and redundant preambles.\n"
        "Keep verbatim (byte-for-byte): fenced code blocks, inline code, file paths, "
        "CLI commands, URLs, tool/model names, section headings, YAML frontmatter.\n"
        "Keep output readable as compact technical prose; do not abbreviate domain terms.\n"
        "Target at least 35% token reduction and do not truncate sections.\n"
        "Output compressed document only (no commentary or preamble).\n\n"
        "Original content:\n"
        f"{original}"
    )


def build_fix_prompt(original: str, compressed: str, errors: list[str]) -> str:
    """Build a targeted repair prompt for validation failures."""

    error_lines = "\n".join(f"- {error}" for error in errors)
    return (
        "The previous compression failed validation.\n"
        "Fix the listed issues. Meaning and completeness take priority over token "
        "reduction — restore any content that was removed to achieve compression.\n"
        "Keep verbatim (byte-for-byte): fenced code blocks, inline code, file paths, "
        "CLI commands, URLs, tool/model names, section headings, YAML frontmatter.\n"
        "Do not add commentary or preamble; output the corrected compressed document only.\n\n"
        "Validation errors:\n"
        f"{error_lines}\n\n"
        "Original content:\n"
        f"{original}\n\n"
        "Current compressed content:\n"
        f"{compressed}"
    )
