"""Heuristic `# AI:` placement suggestions for autofix (not auto-applied)."""

from __future__ import annotations

import re

_ADD_PUBLIC_DEF = re.compile(r"^\+\s*def\s+([a-zA-Z_]\w*)\s*\(")


def collect_autofix_ai_comment_suggestions(diff_text: str) -> list[dict[str, str]]:
    """Suggest `# AI:` for new public defs when the diff adds no nearby AI comment."""
    suggestions: list[dict[str, str]] = []
    current_file = ""
    hunk_lines: list[str] = []

    def flush_hunk() -> None:
        nonlocal hunk_lines, suggestions, current_file
        if current_file.endswith(".py") and hunk_lines:
            suggestions.extend(_suggestions_for_python_hunk(current_file, hunk_lines))
        hunk_lines = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush_hunk()
            current_file = ""
            continue
        if line.startswith("+++ b/"):
            flush_hunk()
            current_file = line[6:].strip()
            continue
        if line.startswith("@@"):
            flush_hunk()
            continue
        if current_file.endswith(".py"):
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                continue
            if len(line) >= 2 and line[0] in " +-":
                if line.startswith("\\"):
                    continue
                hunk_lines.append(line)
    flush_hunk()
    return suggestions


def _suggestions_for_python_hunk(
    path: str, hunk_lines: list[str]
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for i, line in enumerate(hunk_lines):
        if not line.startswith("+"):
            continue
        m = _ADD_PUBLIC_DEF.match(line)
        if not m:
            continue
        name = m.group(1)
        if name.startswith("_"):
            continue
        if _hunk_has_ai_comment_above(hunk_lines, i):
            continue
        out.append(
            {
                "file": path,
                "kind": "ai_comment_suggestion",
                "message": (
                    f"New public function `{name}` has no `# AI:` comment above it in this "
                    "diff; consider adding one line explaining non-obvious intent."
                ),
            }
        )
    return out


def _hunk_has_ai_comment_above(hunk_lines: list[str], def_idx: int) -> bool:
    """True if a `# AI:` appears in a few lines above the added def in this hunk."""
    start = max(0, def_idx - 8)
    for j in range(def_idx - 1, start - 1, -1):
        line = hunk_lines[j]
        if len(line) < 2:
            continue
        kind, body = line[0], line[1:]
        if kind not in "+ ":
            continue
        stripped = body.lstrip()
        if stripped.startswith("# AI:") or stripped.startswith("#AI:"):
            return True
    return False
