"""Build the ## Recently Ingested Sources section for cortex://context."""

from __future__ import annotations

from pathlib import Path

_RECENT_SOURCE_LIMIT = 5
_MAX_TITLE_LEN = 120


def _normalize_title(value: str) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) > _MAX_TITLE_LEN:
        return f"{collapsed[: _MAX_TITLE_LEN - 3]}..."
    return collapsed


def _extract_title_from_markdown(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        return _normalize_title(stripped) if stripped else None
    return None


def _title_from_slug(path: Path) -> str:
    words = [w for w in path.stem.split("-") if w and not w.isdigit()]
    if not words:
        return path.stem
    return " ".join(word.capitalize() for word in words)


def build_recent_ingested_sources_markdown(memory_bank_dir: Path) -> str | None:
    """Return markdown for ## Recently Ingested Sources, or None if no sources exist.

    ``memory_bank_dir`` is any project root-relative tree that contains a ``sources/``
    directory of ``*.md`` snapshots (typically ``.cortex/memory-bank`` or ``.cortex/wiki``).
    """
    sources_dir = memory_bank_dir / "sources"
    if not sources_dir.is_dir():
        return None

    pairs: list[tuple[Path, float]] = []
    for source_path in sources_dir.glob("*.md"):
        try:
            st = source_path.stat()
        except OSError:
            continue
        pairs.append((source_path, st.st_mtime))
    if not pairs:
        return None

    # AI: Secondary sort key (path name) breaks ties deterministically when
    # mtimes collide — see matching fix in recent_artifacts_context.py.
    pairs.sort(key=lambda item: (-item[1], item[0].name))
    top = pairs[:_RECENT_SOURCE_LIMIT]
    lines: list[str] = ["## Recently Ingested Sources", ""]
    for path, _mtime in top:
        title = _extract_title_from_markdown(path) or _title_from_slug(path)
        rel = path.relative_to(memory_bank_dir).as_posix()
        lines.append(f"- [{title}]({rel})")
    return "\n".join(lines)
