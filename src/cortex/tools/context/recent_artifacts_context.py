"""Build the Recent Artifacts section from canonical review, analysis, and query pages."""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.artifacts.artifact_types import get_artifact_directories

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


def build_recent_artifacts_markdown(project_root: Path) -> str | None:
    """Return markdown for ## Recent Artifacts, or None if there is nothing to show."""
    pairs: list[tuple[Path, float]] = []
    for directory in get_artifact_directories(project_root):
        pairs.extend(_iter_markdown_files(directory))
    if not pairs:
        return None
    # AI: Secondary sort key (path name) breaks ties deterministically when
    # mtimes collide (common with fast-created fixtures/low-resolution
    # filesystem clocks) — glob() order alone is not stable across processes,
    # which would otherwise defeat cortex://context's Anthropic prompt-cache
    # exact-prefix matching.
    pairs.sort(key=lambda t: (-t[1], t[0].name))
    top = pairs[:_RECENT_ARTIFACT_LIMIT]
    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    lines: list[str] = ["## Recent Artifacts", ""]
    for path, _mtime in top:
        rel = Path("..") / path.relative_to(memory_bank_dir.parent)
        summary = _one_line_summary_from_markdown(path)
        lines.append(f"- [{rel.as_posix()}]({rel.as_posix()}) — {summary}")
    return "\n".join(lines)
