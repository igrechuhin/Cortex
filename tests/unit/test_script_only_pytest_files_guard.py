"""
Guard: every ``tests/**/test_*.py`` must define pytest-collectable tests.

Files named ``test_*.py`` imply CI coverage. Script-only modules that only assert
under ``if __name__ == "__main__"`` are not collected and can ship without
regression signal.

**Allowlist**: add repo-relative POSIX paths only after human review; note the
reason in a comment next to ``ALLOWLIST`` in this module.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Reviewed exceptions (must remain rare). Empty unless a file is intentionally
# non-collected but kept under tests/ for tooling compatibility.
ALLOWLIST: frozenset[str] = frozenset()


def _collect_test_definitions(module: ast.Module) -> list[str]:
    found: list[str] = []
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                found.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("test_"):
                        found.append(f"{node.name}.{item.name}")
    return found


def _tests_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_no_script_only_test_modules() -> None:
    tests_dir = _tests_root()
    root = tests_dir.parent
    offenders: list[str] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert isinstance(tree, ast.Module)
        if not _collect_test_definitions(tree):
            offenders.append(rel)
    assert not offenders, (
        "These test_*.py files define no collected tests "
        f"(add ``def test_*`` / ``class Test*`` or extend ALLOWLIST): {offenders}"
    )
