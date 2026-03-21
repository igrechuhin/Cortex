"""Validate internal relative markdown links in docs and top-level policy files.

Scopes match the CI markdown link step: ``docs/**/*.md``, root ``README.md``,
``AGENTS.md``, and ``CLAUDE.md``. Skips fenced code blocks, external URLs, and
``cortex://`` targets.
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Doc examples like "[text](target.md)" — not real navigation targets.
_PLACEHOLDER_LINK_TEXT = frozenset({"text"})
_PLACEHOLDER_TARGET_RE = re.compile(r"^(target|path|file)(\.md)?(#.*)?$", re.IGNORECASE)

# Protocols / schemes to ignore (not filesystem paths).
_SKIP_PREFIXES: tuple[str, ...] = (
    "http://",
    "https://",
    "mailto:",
    "cortex://",
    "javascript:",
    "data:",
    "tel:",
    "vscode:",
    "file:",
)


@dataclass(frozen=True, slots=True)
class BrokenLink:
    """One unresolved relative markdown target."""

    source_file: str
    line: int
    target: str


def strip_inline_link_title(raw: str) -> str:
    """Remove optional ` "title"` suffix from a markdown inline link destination."""
    t = raw.strip()
    # Title is separated by ASCII space + double-quote (CommonMark).
    if len(t) > 2 and ' "' in t:
        t = t.split(' "', 1)[0].strip()
    return t


def should_skip_target(raw: str) -> bool:
    """Return True when the link target is not a relative file path to check."""
    t = strip_inline_link_title(raw)
    if not t or t.startswith("#"):
        return True
    lower = t.lower()
    if lower.startswith("//"):
        return True
    return any(lower.startswith(p) for p in _SKIP_PREFIXES)


def is_doc_placeholder_link(link_text: str, path_part: str) -> bool:
    """True for common API-doc pattern examples, not real repo links."""
    if link_text.strip() not in _PLACEHOLDER_LINK_TEXT:
        return False
    return bool(_PLACEHOLDER_TARGET_RE.match(path_part.strip()))


def _path_and_fragment(target: str) -> tuple[str, str]:
    """Split ``path#frag`` after unquoting; return path and fragment."""
    decoded = urllib.parse.unquote(target.strip())
    if "#" in decoded:
        path_part, frag = decoded.split("#", 1)
        return path_part.strip(), frag.strip()
    return decoded.strip(), ""


def _iter_prose_lines(content: str) -> list[tuple[int, str]]:
    """Yield (line_no, line) for lines outside fenced code blocks."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((i, line))
    return out


def resolve_exists(project_root: Path, source: Path, path_part: str) -> bool:
    """Return True if path_part resolves to an existing file or directory."""
    if not path_part:
        return True
    base = source.parent
    candidate = (base / path_part).resolve()
    try:
        _ = candidate.relative_to(project_root.resolve())
    except ValueError:
        return False
    return candidate.is_file() or candidate.is_dir()


def collect_markdown_files_for_link_check(project_root: Path) -> list[Path]:
    """List markdown files to scan (CI scope)."""
    files: list[Path] = []
    docs = project_root / "docs"
    if docs.is_dir():
        for p in docs.rglob("*.md"):
            if not p.is_file():
                continue
            files.append(p)
    for name in ("README.md", "AGENTS.md", "CLAUDE.md"):
        path = project_root / name
        if path.is_file():
            files.append(path)
    return sorted(set(files))


def find_broken_links(project_root: Path) -> list[BrokenLink]:
    """Scan scoped markdown files; return broken relative link records."""
    broken: list[BrokenLink] = []
    root = project_root.resolve()
    for md_path in collect_markdown_files_for_link_check(root):
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_source = str(md_path.relative_to(root))
        for line_no, line in _iter_prose_lines(text):
            for match in _LINK_RE.finditer(line):
                link_text = match.group(1)
                raw_target = match.group(2).strip()
                if should_skip_target(raw_target):
                    continue
                path_part, _frag = _path_and_fragment(
                    strip_inline_link_title(raw_target)
                )
                if not path_part:
                    continue
                if is_doc_placeholder_link(link_text, path_part):
                    continue
                if not resolve_exists(root, md_path, path_part):
                    broken.append(
                        BrokenLink(
                            source_file=rel_source,
                            line=line_no,
                            target=raw_target,
                        )
                    )
    return broken


def format_broken_links_report(violations: list[BrokenLink]) -> str:
    """Human-readable multi-line report."""
    lines = [
        f"{b.source_file}:{b.line}: broken link target `{b.target}`" for b in violations
    ]
    return "\n".join(lines)


def run_cli(argv: list[str] | None = None) -> int:
    """CLI entry: exit 0 if no broken links."""
    _ = argv
    root = Path.cwd().resolve()
    violations = find_broken_links(root)
    if not violations:
        return 0
    print(format_broken_links_report(violations), file=sys.stderr)
    return 1


__all__ = [
    "BrokenLink",
    "collect_markdown_files_for_link_check",
    "find_broken_links",
    "format_broken_links_report",
    "run_cli",
]
