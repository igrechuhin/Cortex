#!/usr/bin/env python3
"""Measure Synapse prompt size and cross-file duplication.

Reports per-file token counts for ``.cortex/synapse/prompts/*.md`` and finds
every block of N or more consecutive lines that appears in M or more distinct
prompt files. Used as the evidence gate for the shared-prompt-reference-layer
plan: extraction only proceeds when the extractable share is material.

Usage:
    python scripts/measure_prompt_duplication.py [--min-block 3] [--min-files 3]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

PROMPTS_DIR = Path(".cortex/synapse/prompts")


def estimate_tokens(text: str) -> int:
    """Estimate token count using the standard 4-chars-per-token heuristic."""
    return (len(text) + 3) // 4


@dataclass(frozen=True)
class PromptFile:
    """A single prompt file with its normalized lines."""

    path: Path
    text: str
    lines: tuple[str, ...]

    @property
    def tokens(self) -> int:
        """Estimated token count for the whole file."""
        return estimate_tokens(self.text)


@dataclass
class DuplicateBlock:
    """A block of lines shared by several prompt files."""

    lines: tuple[str, ...]
    occurrences: dict[str, list[int]] = field(
        default_factory=lambda: dict[str, list[int]]()
    )

    @property
    def file_count(self) -> int:
        """Number of distinct files containing the block."""
        return len(self.occurrences)

    @property
    def tokens(self) -> int:
        """Estimated tokens for one copy of the block."""
        return estimate_tokens("\n".join(self.lines))

    @property
    def redundant_tokens(self) -> int:
        """Tokens saved by keeping one copy and referencing the rest."""
        return self.tokens * (self.file_count - 1)


def load_prompts(prompts_dir: Path) -> list[PromptFile]:
    """Load every prompt markdown file in ``prompts_dir``."""
    prompts: list[PromptFile] = []
    for path in sorted(prompts_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        lines = tuple(line.rstrip() for line in text.splitlines())
        prompts.append(PromptFile(path=path, text=text, lines=lines))
    return prompts


def _is_significant(block: Sequence[str]) -> bool:
    """Reject blocks that are only blank lines or trivial punctuation."""
    meaningful = [line for line in block if len(line.strip()) > 3]
    return len(meaningful) >= 2


def find_duplicate_blocks(
    prompts: Iterable[PromptFile], min_block: int, min_files: int
) -> list[DuplicateBlock]:
    """Find maximal-yield blocks of >= min_block lines shared by >= min_files."""
    index: dict[tuple[str, ...], DuplicateBlock] = {}
    for prompt in prompts:
        name = prompt.path.name
        for start in range(len(prompt.lines) - min_block + 1):
            block = prompt.lines[start : start + min_block]
            if not _is_significant(block):
                continue
            entry = index.setdefault(block, DuplicateBlock(lines=block))
            entry.occurrences.setdefault(name, []).append(start + 1)
    duplicates = [b for b in index.values() if b.file_count >= min_files]
    duplicates.sort(key=lambda b: (-b.redundant_tokens, b.lines))
    return duplicates


def _dedupe_overlapping(blocks: list[DuplicateBlock]) -> list[DuplicateBlock]:
    """Drop blocks whose lines are already covered by a higher-yield block."""
    kept: list[DuplicateBlock] = []
    seen: set[str] = set()
    for block in blocks:
        joined = "\n".join(block.lines)
        if any(joined in other for other in seen):
            continue
        seen.add(joined)
        kept.append(block)
    return kept


def build_report(
    prompts: list[PromptFile], blocks: list[DuplicateBlock]
) -> dict[str, object]:
    """Assemble the measurement + duplication report as a plain dict."""
    baseline = sum(p.tokens for p in prompts)
    redundant = sum(b.redundant_tokens for b in blocks)
    return {
        "baseline_total_tokens": baseline,
        "baseline_total_lines": sum(len(p.lines) for p in prompts),
        "file_count": len(prompts),
        "per_file": [
            {"file": p.path.name, "lines": len(p.lines), "tokens": p.tokens}
            for p in sorted(prompts, key=lambda x: -x.tokens)
        ],
        "duplicate_block_count": len(blocks),
        "extractable_tokens": redundant,
        "extractable_pct": round(100.0 * redundant / baseline, 2) if baseline else 0.0,
        "top_blocks": [
            {
                "file_count": b.file_count,
                "tokens_per_copy": b.tokens,
                "redundant_tokens": b.redundant_tokens,
                "files": {k: v for k, v in sorted(b.occurrences.items())},
                "preview": b.lines[0][:100],
            }
            for b in blocks[:25]
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: emit the JSON measurement report on stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--min-block", type=int, default=3)
    _ = parser.add_argument("--min-files", type=int, default=3)
    _ = parser.add_argument("--prompts-dir", type=Path, default=PROMPTS_DIR)
    args = parser.parse_args(argv)

    prompts = load_prompts(args.prompts_dir)
    if not prompts:
        print(f"No prompts found in {args.prompts_dir}", file=sys.stderr)
        return 1
    blocks = _dedupe_overlapping(
        find_duplicate_blocks(prompts, args.min_block, args.min_files)
    )
    print(json.dumps(build_report(prompts, blocks), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
