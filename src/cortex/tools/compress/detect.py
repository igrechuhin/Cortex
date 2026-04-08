"""File-type detection for compression eligibility."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

FileType = Literal["natural_language", "code", "config", "unknown"]

_EXTENSION_TO_TYPE: dict[str, FileType] = {
    ".md": "natural_language",
    ".py": "code",
    ".ts": "code",
    ".js": "code",
    ".json": "config",
    ".yaml": "config",
    ".toml": "config",
}

_CODE_HINT_PREFIXES: tuple[str, ...] = (
    "def ",
    "class ",
    "import ",
    "from ",
    "return ",
    "if ",
    "for ",
    "while ",
    "try:",
    "except ",
)


def _looks_like_code_line(stripped_line: str) -> bool:
    if not stripped_line:
        return False

    if stripped_line.startswith(_CODE_HINT_PREFIXES):
        return True

    punctuation_hits = sum(
        marker in stripped_line for marker in ("{", "}", "(", ")", "=>", "::", ";")
    )
    return punctuation_hits >= 2


def _fallback_detect_from_content(path: Path) -> FileType:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return "unknown"

    non_empty_lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not non_empty_lines:
        return "natural_language"

    code_lines = sum(_looks_like_code_line(line) for line in non_empty_lines)
    code_ratio = code_lines / len(non_empty_lines)
    # AI: Keep fallback conservative so only strongly code-like files classify as code.
    if code_ratio > 0.6:
        return "code"
    return "natural_language"


def detect_file_type(path: Path) -> FileType:
    """Detect file type used by compression eligibility checks."""

    suffix = path.suffix.lower()
    if suffix in _EXTENSION_TO_TYPE:
        return _EXTENSION_TO_TYPE[suffix]
    return _fallback_detect_from_content(path)
