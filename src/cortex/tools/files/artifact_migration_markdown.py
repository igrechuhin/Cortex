"""Destination offsets respecting Markdown code and balanced path syntax."""

from __future__ import annotations

import re

from cortex.linking.parser import LinkParser

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_INLINE_CODE = re.compile(r"(`+)(?!`)(.*?)\1(?!`)", re.DOTALL)
_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]*", re.MULTILINE)
_ESCAPE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")
_BARE_SPECIAL = re.compile(r"([\\()\[\]])")


def unescape_destination(target: str) -> str:
    return _ESCAPE.sub(r"\1", target)


def escape_destination(target: str) -> str:
    """Retain escaped bare-destination syntax when an authored path changes."""
    return _BARE_SPECIAL.sub(r"\\\1", target)


def _code_mask(text: str) -> str:
    """Retain offsets while excluding fenced, indented and inline code content."""
    chunks: list[str] = []
    fence = ""
    size = 0
    for line in text.splitlines(keepends=True):
        match = _FENCE.match(line.rstrip("\r\n"))
        hidden = bool(fence) or line.startswith(("    ", "\t"))
        if match and not hidden:
            fence, size = match.group(1)[0], len(match.group(1))
            hidden = True
        elif (
            match
            and fence
            and match.group(1)[0] == fence
            and len(match.group(1)) >= size
            and not match.group(2).strip()
        ):
            fence = ""
        chunks.append(
            "".join(char if char in "\r\n" else " " for char in line)
            if hidden
            else line
        )
    masked = "".join(chunks)
    return _INLINE_CODE.sub(lambda match: " " * len(match.group()), masked)


def _destination_end(text: str, start: int) -> int | None:
    """Find a complete angle destination or balanced bare destination, not its title."""
    if start >= len(text):
        return None
    angled = text[start] == "<"
    depth = 0
    index = start + 1 if angled else start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if angled and char == ">":
            return index + 1
        if not angled:
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    return index
                depth -= 1
            elif char.isspace() and depth == 0:
                return index
        if char in "\r\n":
            return None
        index += 1
    return index if not angled and depth == 0 else None


def _escaped_at(text: str, index: int) -> bool:
    prefix = text[:index]
    return (len(prefix) - len(prefix.rstrip("\\"))) % 2 == 1


def destination_spans(text: str) -> list[tuple[int, int]]:
    """Reuse crosslink syntax discovery, then extend destinations past balanced parentheses."""
    masked = _code_mask(text)
    parser = LinkParser()
    starts = [
        match.start(2)
        for match in parser.link_pattern.finditer(masked)
        if not _escaped_at(masked, match.start())
    ]
    starts += [match.end() for match in _DEFINITION.finditer(masked)]
    result: set[tuple[int, int]] = set()
    for start in starts:
        while start < len(masked) and masked[start] in " \t":
            start += 1
        end = _destination_end(masked, start)
        if end is not None and end > start:
            result.add((start + 1, end - 1) if masked[start] == "<" else (start, end))
    for match in parser.transclusion_pattern.finditer(masked):
        start, end = match.span(1)
        raw = text[start:end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        result.add((start + left, start + right))
    return sorted(result)
