"""Enforce tracked references in unconditional skip markers (plan cleanup)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from pytest import Item


def skip_reason_has_tracked_reference(reason: str | None) -> bool:
    """Return True if *reason* contains ref:, issue:, or see … <token> pattern."""
    if reason is None:
        return False
    stripped = reason.strip()
    if not stripped:
        return False
    if re.search(r"\bref:\s*[A-Za-z0-9_-]+", stripped, re.IGNORECASE):
        return True
    if re.search(r"\bissue:\s*#?[A-Za-z0-9_-]+", stripped, re.IGNORECASE):
        return True
    if re.search(r"\bsee\b", stripped, re.IGNORECASE):
        if re.search(r"\bsee\b\s+plan:\s*[A-Za-z0-9_-]+", stripped, re.IGNORECASE):
            return True
        if re.search(r"\bsee\b\s+[A-Za-z0-9_-]{3,}\b", stripped, re.IGNORECASE):
            return True
        if re.search(
            r"\bsee\b.{0,300}?\b([A-Za-z0-9_-]{3,})\b",
            stripped,
            re.IGNORECASE | re.DOTALL,
        ):
            return True
    return False


def describe_skip_policy_violation(nodeid: str, reason: str | None) -> str:
    """Human-readable error for a missing skip reference."""
    if reason is None or not str(reason).strip():
        return f"{nodeid}: @pytest.mark.skip requires a non-empty reason that includes ref:, issue:, or see <plan-or-issue-token> (see tests/skip_reference_policy.py)."
    return f"{nodeid}: @pytest.mark.skip reason must include ref:, issue:, or see <token> (got: {reason!r})."


def enforce_unconditional_skip_markers(items: list[Item]) -> None:
    """Raise pytest.UsageError if any collected item has an invalid skip marker."""
    import pytest

    for item in items:
        skip_marker = item.get_closest_marker("skip")
        if skip_marker is None:
            continue
        reason = skip_marker.kwargs.get("reason")
        if skip_marker.args:
            first = skip_marker.args[0]
            if isinstance(first, str) and reason is None:
                reason = first
        if skip_reason_has_tracked_reference(
            reason if isinstance(reason, str) else None
        ):
            continue
        msg = describe_skip_policy_violation(
            item.nodeid, reason if isinstance(reason, str) else None
        )
        raise pytest.UsageError(msg)


def _static_skip_reason_text(expr: ast.expr) -> str | None:
    """Return text used to validate ref patterns, or None if not statically known."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.JoinedStr):
        parts: list[str] = []
        for part in expr.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
        return "".join(parts) if parts else None
    return None


class _PytestSkipCallVisitor(ast.NodeVisitor):
    """Find ``pytest.skip`` / ``skip`` calls and validate reasons via static text."""

    def __init__(self, rel_path: str) -> None:
        self._rel_path = rel_path
        self._pytest_names: set[str] = set()
        self._skip_names: set[str] = set()
        self.violations: list[tuple[int, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "pytest":
                self._pytest_names.add(alias.asname or "pytest")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "pytest":
            for alias in node.names:
                if alias.name == "skip":
                    self._skip_names.add(alias.asname or "skip")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_pytest_skip_call(node):
            self._check_skip_call(node)
        self.generic_visit(node)

    def _is_pytest_skip_call(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "skip":
            if isinstance(func.value, ast.Name) and func.value.id in self._pytest_names:
                return True
        if isinstance(func, ast.Name) and func.id in self._skip_names:
            return True
        return False

    def _check_skip_call(self, node: ast.Call) -> None:
        reason_expr: ast.expr | None = None
        if node.args:
            reason_expr = node.args[0]
        else:
            for kw in node.keywords:
                if kw.arg == "reason":
                    reason_expr = kw.value
                    break
        if reason_expr is None:
            loc = f"{self._rel_path}:{node.lineno}"
            msg = f"{loc}: pytest.skip() requires a reason string (literal or f-string) with ref:, issue:, or see <token>."
            self.violations.append((node.lineno, msg))
            return
        static = _static_skip_reason_text(reason_expr)
        if static is None:
            loc = f"{self._rel_path}:{node.lineno}"
            msg = f"{loc}: pytest.skip reason must be a string literal or f-string whose literal segments include ref:, issue:, or see <token>."
            self.violations.append((node.lineno, msg))
            return
        if skip_reason_has_tracked_reference(static):
            return
        loc = f"{self._rel_path}:{node.lineno}"
        msg = f"{loc}: pytest.skip reason must include ref:, issue:, or see <token> (static segment: {static!r})."
        self.violations.append((node.lineno, msg))


def collect_runtime_pytest_skip_violations_from_source(
    source: str, *, rel_path: str
) -> list[tuple[int, str]]:
    """Parse *source* and return (line, message) violations for ``pytest.skip`` calls."""
    tree = ast.parse(source, filename=rel_path)
    visitor = _PytestSkipCallVisitor(rel_path)
    visitor.visit(tree)
    return visitor.violations


def collect_runtime_pytest_skip_violations_under(tests_root: Path) -> list[str]:
    """Scan ``tests_root`` (recursively) for invalid runtime ``pytest.skip`` usage."""
    messages: list[str] = []
    root = tests_root.resolve()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root.parent).as_posix()
        text = path.read_text(encoding="utf-8")
        try:
            violations = collect_runtime_pytest_skip_violations_from_source(
                text, rel_path=rel
            )
        except SyntaxError as exc:
            messages.append(f"{rel}: cannot parse ({exc})")
            continue
        for _line, msg in sorted(violations, key=lambda x: x[0]):
            messages.append(msg)
    return messages


def enforce_runtime_pytest_skip_in_tests_tree(tests_root: Path) -> None:
    """Fail collection if any test file uses ``pytest.skip`` without a tracked reason."""
    import pytest

    messages = collect_runtime_pytest_skip_violations_under(tests_root)
    if not messages:
        return
    detail = "\n".join(messages)
    raise pytest.UsageError("pytest.skip policy violations (runtime calls):\n" + detail)
