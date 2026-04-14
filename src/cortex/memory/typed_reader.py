"""Read typed memory entries from markdown files."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.memory.memory_types import MemoryEntry, MemoryType, classify_text

_TYPE_COMMENT_RE = re.compile(r"<!--\s*memory_type:\s*([a-z_]+)\s*-->", re.IGNORECASE)


class TypedMemoryReader:
    def read_all(self, file_path: Path) -> list[MemoryEntry]:
        if not file_path.exists():
            return []
        content = file_path.read_text(encoding="utf-8")
        if not content.strip():
            return []
        paragraphs = [
            part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()
        ]
        entries: list[MemoryEntry] = []
        pending_type: MemoryType | None = None
        for paragraph in paragraphs:
            match = _TYPE_COMMENT_RE.fullmatch(paragraph)
            if match is not None:
                pending_type = _parse_memory_type(match.group(1))
                continue
            memory_type = pending_type or classify_text(paragraph)
            entries.append(MemoryEntry(content=paragraph, memory_type=memory_type))
            pending_type = None
        return entries

    def read_by_type(
        self, file_path: Path, memory_type: MemoryType
    ) -> list[MemoryEntry]:
        return [
            entry
            for entry in self.read_all(file_path)
            if entry.memory_type == memory_type
        ]


def _parse_memory_type(raw_value: str) -> MemoryType:
    try:
        return MemoryType(raw_value.lower())
    except ValueError:
        return MemoryType.STATUS
