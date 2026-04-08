"""Word-count / token-budget hints for project memory files."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

# AI: Aligns with analyze prompt guidance for “large” memory-bank prose.
_WORD_COMPRESSION_THRESHOLD = 500


class TokenBudgetEntry(BaseModel):
    """Per-file word count and compression candidacy."""

    path: str
    word_count: int
    is_candidate: bool = Field(
        description="True when word_count exceeds the compression threshold."
    )


def iter_memory_bank_text_paths(project_root: Path) -> list[Path]:
    """Paths scanned for token budget and compress_memory_bank (same order)."""
    targets: list[Path] = []
    claude = project_root / "CLAUDE.md"
    if claude.is_file():
        targets.append(claude)
    mb = project_root / ".cortex" / "memory-bank"
    if mb.is_dir():
        for p in sorted(mb.glob("*.md")):
            if p.name == "roadmap.md":
                continue
            if ".original" in p.name:
                continue
            targets.append(p)
    claude_alt = project_root / ".claude" / "CLAUDE.md"
    if claude_alt.is_file():
        targets.append(claude_alt)
    return targets


def _word_count(text: str) -> int:
    return len(text.split())


def compute_token_budget(project_root: Path) -> list[TokenBudgetEntry]:
    """Collect word counts for memory files that affect session load."""
    entries: list[TokenBudgetEntry] = []
    for path in iter_memory_bank_text_paths(project_root):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        wc = _word_count(content)
        entries.append(
            TokenBudgetEntry(
                path=str(path.relative_to(project_root)).replace("\\", "/"),
                word_count=wc,
                is_candidate=wc > _WORD_COMPRESSION_THRESHOLD,
            )
        )
    return entries


def format_token_budget_report(entries: list[TokenBudgetEntry]) -> str:
    """Markdown table + optional recommendation for analyze / cortex://analysis."""
    if not entries:
        return "No memory files scanned (or paths unreadable).\n"

    lines = [
        "| File | Words | Status |",
        "|------|-------|--------|",
    ]
    any_candidate = False
    for e in entries:
        if e.is_candidate:
            any_candidate = True
            status = "⚠ compression candidate (>500)"
        else:
            status = "✓"
        lines.append(f"| {e.path} | {e.word_count} | {status} |")
    out = "\n".join(lines) + "\n"
    if any_candidate:
        out += "\nRun compress_memory_bank() to reduce session token cost.\n"
    return out
