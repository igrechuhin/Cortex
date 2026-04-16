"""Language-parametrized reflection checklist text for the quality gate.

Avoids importing the heavy ``evaluation`` package ``__init__`` from the rules
resource path. Checklist bodies are split by language so callers can attach only
relevant sections (diff-derived) or the full catalog (``cortex://rules``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Ordered display order for the full catalog (rules resource).
REFLECTION_LANGUAGE_ORDER: tuple[str, ...] = (
    "python",
    "swift",
    "typescript",
    "javascript",
    "go",
    "rust",
    "markdown",
)

# Maps file suffix (lowercase, with dot) → reflection language id.
_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".md": "markdown",
    ".mdc": "markdown",
}

_DIFF_PATH_LINE = re.compile(r"^\+\+\+ b/(.+)$")
_DIFF_GIT_LINE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


REFLECTION_GENERAL_MARKDOWN = """## Reflection Checklist

Cortex can run an optional **reflection pass** after the primary quality gate. Critiques use five categories (all languages):

- **logic** — Control flow, unsound assumptions, or missing branches that automated checks may miss.
- **security** — Validation gaps, secrets/credentials, injection or unsafe deserialization in changed code.
- **edge_case** — Empty inputs, error paths, boundaries, or concurrency hazards.
- **test_coverage** — New or changed public surface without tests, or critical paths not exercised.
- **docs** — Behavior changed without documentation; TODO/FIXME in production paths.

The sections below list **language-specific** cues the heuristics may use when those file types appear in the diff.

Reflection supplements the quality gate; it does not replace tests or typechecking.
"""

# Markdown fragment per language id (no top-level ## — combined under the general block).
_LANGUAGE_SECTIONS: dict[str, str] = {
    "python": """### Python

- **logic**: `try:` in added lines without `except`/`finally` in the same diff.
- **docs / coverage**: TODO/FIXME/HACK in added lines; new top-level `def` under `src/` without test path changes in the diff.
- **docs / annotations**: `# BELIEF:` left as context while other lines in the hunk change (possible stale assumption).
- **docs / annotations**: dict key access on untyped variables or chained attribute access in added lines triggers a suggestion to add a BELIEF annotation.
- **security**: Secret-like assignments (`password=`, `api_key=`, etc.) in literals.""",
    "swift": """### Swift

- **logic / concurrency**: `try!`, force-unwraps, or missing `guard`/`throw` paths on failure-prone APIs; `@MainActor` / `Sendable` mismatches when crossing actors.
- **edge_case**: `Task {}` or async entry points without cancellation or error handling where the API requires it.
- **security**: Hardcoded tokens or URLs with embedded credentials in changed lines.""",
    "typescript": """### TypeScript / TSX

- **logic**: Empty `catch` blocks or swallowed errors; unsafe `as` casts hiding type holes.
- **edge_case**: Missing `null`/`undefined` handling for external inputs.
- **security**: Secrets in source; unsafe `innerHTML` or dynamic code eval when the diff touches DOM/script code.""",
    "javascript": """### JavaScript / JSX

- Same cues as TypeScript where applicable: empty catches, loose equality on security-sensitive checks, secrets in literals.""",
    "go": """### Go

- **logic**: Ignored errors (`_, _ =` or `_ = err`) on operations that must be handled; missing `defer` cleanup for resources the diff introduces.
- **edge_case**: Goroutine leaks — `go` without cancellation or lifecycle tied to parent context.""",
    "rust": """### Rust

- **logic / edge_case**: `unwrap()` / `expect()` on `Result`/`Option` where the diff adds fallible paths; `TODO` in non-test code.
- **security**: `unsafe` blocks expanding without invariants documented in the diff.""",
    "markdown": """### Markdown / docs

- **docs**: Broken relative links or heading anchors; frontmatter/schema drift when the diff edits indexed docs.""",
}


def detect_languages_in_diff(diff_text: str) -> list[str]:
    """Infer reflection language ids from paths appearing in unified diff text.

    Returns a de-duplicated, stable-ordered list. Empty when no recognized paths
    are found (callers may still run language-agnostic heuristics).
    """
    paths: list[str] = []
    for line in diff_text.splitlines():
        m = _DIFF_PATH_LINE.match(line)
        if m:
            paths.append(m.group(1).strip())
            continue
        m2 = _DIFF_GIT_LINE.match(line)
        if m2:
            paths.append(m2.group(2).strip())

    langs: set[str] = set()
    for path in paths:
        lower = path.lower()
        for ext, lang in _EXTENSION_TO_LANGUAGE.items():
            if lower.endswith(ext):
                langs.add(lang)
                break

    order = {k: i for i, k in enumerate(REFLECTION_LANGUAGE_ORDER)}
    return sorted(langs, key=lambda x: (order.get(x, 999), x))


def build_reflection_checklist_markdown(
    languages: Iterable[str] | None = None,
    *,
    include_full_catalog: bool = False,
) -> str:
    """Build the markdown checklist for reflection.

    - ``include_full_catalog=True`` or ``languages is None``: general intro plus
      every language section (for ``cortex://rules`` and the default
      ``REFLECTION_CHECKLIST_MARKDOWN`` export).
    - ``languages`` non-empty: general intro plus only those language sections
      (typically from :func:`detect_languages_in_diff`). Unknown ids are ignored.
    - ``languages`` empty (and not full catalog): general intro only.
    """
    parts: list[str] = [REFLECTION_GENERAL_MARKDOWN.strip()]

    if include_full_catalog or languages is None:
        for lang in REFLECTION_LANGUAGE_ORDER:
            body = _LANGUAGE_SECTIONS.get(lang)
            if body:
                parts.append(body.strip())
        return "\n\n".join(parts) + "\n"

    want = {str(x).strip().lower() for x in languages if str(x).strip()}
    if not want:
        return "\n\n".join(parts) + "\n"

    for lang in REFLECTION_LANGUAGE_ORDER:
        if lang in want and lang in _LANGUAGE_SECTIONS:
            parts.append(_LANGUAGE_SECTIONS[lang].strip())

    return "\n\n".join(parts) + "\n"


# Full catalog for ``cortex://rules`` and tests that need a stable import.
REFLECTION_CHECKLIST_MARKDOWN = build_reflection_checklist_markdown(
    languages=None,
)
