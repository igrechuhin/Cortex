"""Minimal parsed-link edits for moved reports and their incoming references."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from cortex.tools.files.artifact_migration_markdown import (
    destination_spans,
    escape_destination,
    unescape_destination,
)
from cortex.tools.plans.completion_transaction_io import validate_contained_path


def _encode_target_path(target: str, path: str, original: str) -> str:
    encoded = quote(path, safe="/._-~") if "%" in original or " " in path else path
    if "\\" in target and "%" not in original and " " not in path:
        encoded = escape_destination(encoded)
    return encoded


def _relocated_target(
    target: str, source: Path, destination: Path, moves: dict[Path, Path], root: Path
) -> str | None:
    parsed = urlsplit(unescape_destination(target))
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    decoded = unquote(parsed.path)
    absolute = Path(decoded).is_absolute()
    old_target = Path(os.path.abspath(decoded if absolute else source.parent / decoded))
    if not old_target.is_relative_to(root):
        return None  # Authored external references are not migration targets.
    new_target = moves.get(old_target, old_target)
    if old_target not in moves and (absolute or source.parent == destination.parent):
        return None
    validate_contained_path(old_target, root)
    validate_contained_path(new_target, root)
    new_path = (
        str(new_target)
        if absolute
        else Path(os.path.relpath(new_target, destination.parent)).as_posix()
    )
    if os.path.normpath(new_path) == os.path.normpath(decoded):
        return None
    encoded = _encode_target_path(target, new_path, parsed.path)
    return (
        encoded
        + ("?" + parsed.query if parsed.query else "")
        + ("#" + parsed.fragment if parsed.fragment else "")
    )


def rewrite_links(
    content: bytes, source: Path, destination: Path, moves: dict[Path, Path], root: Path
) -> bytes:
    """Change complete parsed destinations only, never prose or code examples."""
    text = content.decode("utf-8")
    replacements: list[tuple[int, int, str]] = []
    for start, end in destination_spans(text):
        target = text[start:end]
        value = _relocated_target(target, source, destination, moves, root)
        if value is not None and value != target:
            replacements.append((start, end, value))
    for start, end, value in sorted(replacements, reverse=True):
        text = text[:start] + value + text[end:]
    return text.encode("utf-8")
