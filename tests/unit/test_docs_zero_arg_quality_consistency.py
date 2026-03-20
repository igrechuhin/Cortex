"""Guard against reintroducing deprecated quality MCP names in onboarding docs."""

from __future__ import annotations

import re
from pathlib import Path

DEPRECATED_QUALITY_MARKERS = (
    "execute_pre_commit_checks",
    "start_quality_job",
    "get_quality_job_status",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _strip_fenced_code_blocks(markdown: str) -> str:
    """Remove ``` ... ``` regions so quoted errors can mention legacy tool names."""
    pattern = re.compile(
        r"(?m)^[ \t]*```[\w]*\r?\n.*?^[ \t]*```\r?\n?",
        re.DOTALL,
    )
    prev = None
    out = markdown
    while prev != out:
        prev = out
        out = pattern.sub("", out)
    return out


def _heading_allows_deprecated_names(heading_line: str) -> bool:
    lower = heading_line.lower()
    return any(k in lower for k in ("legacy", "deprecated", "historical"))


def _section_bodies_to_scan(stripped: str) -> list[str]:
    """Split on level-2 headings only so ### stays inside parent exemption."""
    text = stripped
    header_re = re.compile(r"(?m)^##\s+.+$")
    matches = list(header_re.finditer(text))
    bodies: list[str] = []
    if not matches:
        return [text]
    bodies.append(text[: matches[0].start()])
    for i, m in enumerate(matches):
        heading = m.group(0)
        start_body = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start_body:end]
        if _heading_allows_deprecated_names(heading):
            continue
        bodies.append(body)
    return bodies


def violations_in_markdown(markdown: str) -> list[str]:
    stripped = _strip_fenced_code_blocks(markdown)
    hits: list[str] = []
    for segment in _section_bodies_to_scan(stripped):
        for marker in DEPRECATED_QUALITY_MARKERS:
            if marker in segment:
                hits.append(marker)
    return hits


def _tracked_markdown_paths() -> list[Path]:
    root = _repo_root()
    paths = [root / "README.md", root / "AGENTS.md"]
    paths.extend(sorted((root / "docs").rglob("*.md")))
    return paths


def test_docs_avoid_deprecated_quality_mcp_entrypoints() -> None:
    root = _repo_root()
    failures: list[str] = []
    for path in _tracked_markdown_paths():
        text = path.read_text(encoding="utf-8")
        bad = violations_in_markdown(text)
        if bad:
            rel = path.relative_to(root)
            failures.append(f"{rel}: {sorted(set(bad))}")
    assert not failures, "Deprecated quality entrypoints in docs:\n" + "\n".join(
        failures
    )


def test_violations_ignore_fenced_code() -> None:
    md = "## Intro\nUse `run_quality_gate()`.\n\n```\nexecute_pre_commit_checks\n```\n"
    assert violations_in_markdown(md) == []


def test_legacy_heading_exempts_section_body() -> None:
    md = (
        "## Deprecated names\n\nexecute_pre_commit_checks is documented here.\n\n"
        "## Current\n\nrun_quality_gate() only.\n"
    )
    assert violations_in_markdown(md) == []


def test_non_legacy_section_still_scanned() -> None:
    md = "## Guide\n\nPlease run execute_pre_commit_checks.\n"
    assert "execute_pre_commit_checks" in violations_in_markdown(md)
