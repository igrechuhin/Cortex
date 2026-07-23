"""Prompt-cache payload stability audit for cache-hinted MCP resources.

Anthropic prompt caching relies on exact-prefix byte matching. The
``cortex://rules`` and ``cortex://context`` MCP resources carry
``cache_control`` ``_meta`` hints (see ``src/cortex/core/constants.py``,
``CORTEX_RULES_RESOURCE_READ_META`` / ``CORTEX_CONTEXT_RESOURCE_READ_META``),
so a cache hit requires their payload-construction source to depend only on
persisted file/rule state — never on wall-clock time, random identifiers, or
process identity.

This module scans the source text of those two resource handler files for
constructs that would reintroduce non-determinism (a regression against the
``prompt-cache-payload-stability-for-cached-mcp-resources`` plan) and is wired
into ``execute_quality()`` (the ``quality`` pre-commit check) so a future edit
that reintroduces one of these patterns fails the quality gate automatically.
"""

from __future__ import annotations

import re
from pathlib import Path

# AI: Scoped narrowly to the two cache-hinted resource handler files, per plan
# scope boundary — a codebase-wide scan would false-positive on legitimate
# datetime/uuid usage elsewhere (e.g. audit logs, session-goal timestamps).
CACHE_PAYLOAD_AUDIT_TARGET_FILES: tuple[str, ...] = (
    "src/cortex/tools/optimization/handlers.py",
    "src/cortex/tools/synapse/rules_operations.py",
)

_VOLATILE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("datetime.now() call", re.compile(r"datetime\.now\(")),
    ("time.time() call", re.compile(r"time\.time\(\)")),
    ("uuid1()/uuid4() call", re.compile(r"uuid[14]\(\)")),
    ("os.getpid() call", re.compile(r"getpid\(\)")),
    (
        "raw ISO-timestamp literal",
        re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
    ),
)


def audit_cache_payload_stability(text: str) -> list[str]:
    """Return violation messages for volatile-content patterns found in ``text``.

    Each violation names the matched pattern, the 1-based line number, and
    the offending line. An empty list means no volatile-content patterns
    were found (payload text is stable across repeated reads of unchanged
    state).
    """
    violations: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in _VOLATILE_PATTERNS:
            if pattern.search(line):
                violations.append(
                    f"line {line_number}: {label} matched: {line.strip()}"
                )
    return violations


def check_cache_payload_stability(project_root: Path) -> list[str]:
    """Audit the cache-hinted resource handler files under ``project_root``.

    Missing files are skipped silently (checkouts may not include ``src/``
    under every check invocation), keeping this a no-op fallback rather than
    a hard error.
    """
    violations: list[str] = []
    for rel_path in CACHE_PAYLOAD_AUDIT_TARGET_FILES:
        path = project_root / rel_path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        violations.extend(
            f"{rel_path}:{message}" for message in audit_cache_payload_stability(text)
        )
    return violations
