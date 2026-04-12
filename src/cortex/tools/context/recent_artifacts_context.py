"""Build the ## Recent Artifacts section for cortex://context (filed review/analysis pages)."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.artifacts.artifact_types import MemoryBankArtifactStorageSubdir

# AI: Only reviews/ and analyses/ (per file-review-reports plan); findings/queries stay out of scope here.
_ARTIFACT_SUBDIRS: tuple[MemoryBankArtifactStorageSubdir, ...] = (
    MemoryBankArtifactStorageSubdir.REVIEWS,
    MemoryBankArtifactStorageSubdir.ANALYSES,
)
_RECENT_ARTIFACT_LIMIT = 5
_MAX_SUMMARY_LEN = 200


def _strip_yaml_frontmatter(text: str) -> str:
    """Return markdown body after optional YAML frontmatter."""
    if not text.startswith("---"):
        return text
    rest = text[3:].lstrip("\n")
    close_idx = rest.find("\n---")
    if close_idx == -1:
        return text
    after = rest[close_idx + 4 :]
    return after.lstrip("\n")


def _one_line_summary_from_markdown(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return "(unreadable)"
    body = _strip_yaml_frontmatter(raw)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        collapsed = " ".join(stripped.split())
        if len(collapsed) > _MAX_SUMMARY_LEN:
            return f"{collapsed[: _MAX_SUMMARY_LEN - 3]}..."
        return collapsed
    return "(empty)"


def _iter_markdown_files(subdir: Path) -> list[tuple[Path, float]]:
    if not subdir.is_dir():
        return []
    out: list[tuple[Path, float]] = []
    for p in subdir.glob("*.md"):
        try:
            st = p.stat()
        except OSError:
            continue
        out.append((p, st.st_mtime))
    return out


def build_recent_artifacts_markdown(memory_bank_dir: Path) -> str | None:
    """Return markdown for ## Recent Artifacts, or None if there is nothing to show."""
    pairs: list[tuple[Path, float]] = []
    for subdir in _ARTIFACT_SUBDIRS:
        pairs.extend(_iter_markdown_files(memory_bank_dir / subdir.value))
    if not pairs:
        return None
    pairs.sort(key=lambda t: t[1], reverse=True)
    top = pairs[:_RECENT_ARTIFACT_LIMIT]
    lines: list[str] = ["## Recent Artifacts", ""]
    for path, _mtime in top:
        try:
            rel = path.relative_to(memory_bank_dir)
        except ValueError:
            rel = path
        summary = _one_line_summary_from_markdown(path)
        lines.append(f"- [{rel.as_posix()}]({rel.as_posix()}) — {summary}")
    return "\n".join(lines)
