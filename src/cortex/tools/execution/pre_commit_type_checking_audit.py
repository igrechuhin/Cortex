"""Mechanical enforcement of the ``TYPE_CHECKING`` import ban.

``python-coding-standards.mdc`` forbids ``from typing import TYPE_CHECKING``
and ``if TYPE_CHECKING:`` blocks, twice marked STRICTLY FORBIDDEN, but nothing
in the toolchain looked for the pattern — a violation shipped through pyright,
ruff, the structural gate, the review gate, and the full test suite.

Two mechanisms now enforce it:

* ruff's ``flake8-tidy-imports`` ``banned-api`` entry (``TID251`` in
  ``pyproject.toml``) rejects ``from typing import TYPE_CHECKING`` and
  ``typing.TYPE_CHECKING`` attribute access, surfacing in the editor as well
  as in CI.
* this module, wired into ``execute_quality()``, covers the two cases ruff
  cannot: a bare ``if TYPE_CHECKING:`` block with no matching import, and the
  allowlist policy — a bare ``# noqa: TID251`` silences ruff with no stated
  reason, whereas this check requires an inline justification comment.

Detection runs over code tokens only, so the literal string ``TYPE_CHECKING``
inside a comment or a docstring (as in this module) is never flagged.

Allowlisting a genuinely unavoidable occurrence requires satisfying *both*
mechanisms on the same line — deliberately awkward, so bypassing costs more
than fixing::

    from typing import TYPE_CHECKING  # noqa: TID251  # type-checking-allowed: <reason>

The ``noqa`` alone silences ruff but not this check, and the justification
marker alone silences this check but not ruff; neither shortcut is enough.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

#: Inline justification required to allowlist an occurrence. A bare marker with
#: no reason after the colon does not pass — bypassing must cost more than
#: fixing.
TYPE_CHECKING_ALLOWLIST_MARKER = "# type-checking-allowed:"

#: Source roots scanned by :func:`check_type_checking_ban`.
TYPE_CHECKING_AUDIT_ROOTS: tuple[str, ...] = ("src", "tests")

_BANNED_NAME = "TYPE_CHECKING"
_RULE_CITATION = "python-coding-standards.mdc (TYPE_CHECKING is STRICTLY FORBIDDEN)"
_FIX_HINT = (
    "Use a normal top-level import instead; the import cycle these blocks "
    "claim to break is usually not real."
)
_FALLBACK_PATTERN = re.compile(rf"\b{_BANNED_NAME}\b")


def _is_allowlisted(line: str) -> bool:
    """Return True when ``line`` carries a justification comment with a reason."""
    marker_index = line.find(TYPE_CHECKING_ALLOWLIST_MARKER)
    if marker_index == -1:
        return False
    reason = line[marker_index + len(TYPE_CHECKING_ALLOWLIST_MARKER) :].strip()
    return bool(reason)


def _fallback_line_numbers(text: str) -> list[int]:
    """Regex fallback for sources that cannot be tokenized (syntax errors).

    Comment-only lines are skipped so an unparseable file still gets the same
    comment/docstring leniency as the tokenizer path for the common case.
    """
    return [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if not line.lstrip().startswith("#") and _FALLBACK_PATTERN.search(line)
    ]


def _code_line_numbers(text: str) -> list[int]:
    """Return de-duplicated 1-based lines where the banned name appears as code."""
    readline = io.StringIO(text).readline
    hits: dict[int, None] = {}
    try:
        for token in tokenize.generate_tokens(readline):
            if token.type == tokenize.NAME and token.string == _BANNED_NAME:
                hits[token.start[0]] = None
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return _fallback_line_numbers(text)
    return list(hits)


def audit_type_checking_usage(text: str) -> list[str]:
    """Return violation messages for banned ``TYPE_CHECKING`` usage in ``text``.

    Each message names the 1-based line, cites the rule, states the usual fix,
    and quotes the offending line. Allowlisted lines and occurrences appearing
    only in comments or string literals are excluded.
    """
    lines = text.splitlines()
    violations: list[str] = []
    for line_number in _code_line_numbers(text):
        line = lines[line_number - 1] if line_number <= len(lines) else ""
        if _is_allowlisted(line):
            continue
        message = f"line {line_number}: {_BANNED_NAME} is banned by {_RULE_CITATION}."
        violations.append(f"{message} {_FIX_HINT} Offending line: {line.strip()}")
    return violations


def _audit_file(project_root: Path, path: Path) -> list[str]:
    """Audit a single Python file, prefixing messages with its relative path."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    # AI: Cheap substring pre-filter — tokenizing every file under src/ and
    # tests/ on each quality-gate run would dominate the gate's runtime.
    if _BANNED_NAME not in text:
        return []
    relative = path.relative_to(project_root).as_posix()
    return [f"{relative}:{message}" for message in audit_type_checking_usage(text)]


def check_type_checking_ban(project_root: Path) -> list[str]:
    """Scan ``src/`` and ``tests/`` under ``project_root`` for banned usage.

    Missing roots are skipped silently so the check degrades to a no-op rather
    than a hard error in partial checkouts.
    """
    violations: list[str] = []
    for root_name in TYPE_CHECKING_AUDIT_ROOTS:
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            violations.extend(_audit_file(project_root, path))
    return violations
