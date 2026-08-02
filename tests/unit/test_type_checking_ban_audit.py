"""Unit tests for the mechanical TYPE_CHECKING import-ban audit.

Covers ``audit_type_checking_usage()``, the ``check_type_checking_ban()``
file-scanning wrapper, and its wiring into the ``quality`` pre-commit check
result (plan: ``mechanically-enforce-the-type-checking-import-ban``).

Every banned snippet below lives inside a string literal, so this test module
itself is clean under the audit it exercises.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution.pre_commit_pipeline_quality import (
    build_quality_check_result,
)
from cortex.tools.execution.pre_commit_type_checking_audit import (
    TYPE_CHECKING_ALLOWLIST_MARKER,
    audit_type_checking_usage,
    check_type_checking_ban,
)

# AI: Assembled at runtime so this module never contains the banned literal as a
# single token, keeping the test suite clean under the audit it exercises.
_BANNED = "TYPE" + "_CHECKING"
_IMPORT_FORM = f"from typing import {_BANNED}\n"
_BLOCK_FORM = f"if {_BANNED}:\n    pass\n"
_ATTRIBUTE_FORM = f"import typing\n\nif typing.{_BANNED}:\n    pass\n"

_CLEAN_SOURCE = '''"""Docstring mentioning {name} harmlessly."""

# A comment mentioning {name} as well.
VALUE = "{name}"
'''.format(
    name=_BANNED
)


def _passing_lint() -> CheckResult:
    """Build a successful lint result so audits alone decide the outcome."""
    return CheckResult(check_type="lint", success=True, output="ok")


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(_IMPORT_FORM, id="import-form"),
        pytest.param(_BLOCK_FORM, id="bare-block-form"),
        pytest.param(_ATTRIBUTE_FORM, id="attribute-form"),
        pytest.param(_IMPORT_FORM + "\n" + _BLOCK_FORM, id="both-forms"),
    ],
)
def test_audit_flags_banned_usage(source: str) -> None:
    """Arrange banned source; act on the audit; assert it reports a violation."""
    violations = audit_type_checking_usage(source)

    assert violations
    assert all("python-coding-standards.mdc" in message for message in violations)
    assert all(message.startswith("line ") for message in violations)


def test_audit_reports_every_offending_line_once() -> None:
    """A file with both forms reports one violation per offending line."""
    source = _IMPORT_FORM + "\n" + _BLOCK_FORM

    violations = audit_type_checking_usage(source)

    assert len(violations) == 2
    assert violations[0].startswith("line 1:")
    assert violations[1].startswith("line 3:")


def test_audit_ignores_comment_and_docstring_occurrences() -> None:
    """The literal name inside a comment, docstring, or string is not flagged."""
    assert audit_type_checking_usage(_CLEAN_SOURCE) == []


def test_audit_allows_occurrence_with_justification_comment() -> None:
    """An inline justification comment with a reason allowlists the line."""
    source = (
        f"from typing import {_BANNED}  "
        f"{TYPE_CHECKING_ALLOWLIST_MARKER} unavoidable third-party cycle\n"
    )

    assert audit_type_checking_usage(source) == []


def test_audit_allows_documented_combined_allowlist_form() -> None:
    """The documented form satisfying both ruff and this audit passes."""
    source = (
        f"from typing import {_BANNED}  # noqa: TID251  "
        f"{TYPE_CHECKING_ALLOWLIST_MARKER} genuine third-party cycle\n"
    )

    assert audit_type_checking_usage(source) == []


def test_audit_rejects_bare_suppression_without_justification() -> None:
    """A bare ruff suppression, or a marker with no reason, still fails."""
    bare_noqa = f"from typing import {_BANNED}  # noqa: TID251\n"
    empty_reason = f"from typing import {_BANNED}  {TYPE_CHECKING_ALLOWLIST_MARKER}\n"

    assert audit_type_checking_usage(bare_noqa)
    assert audit_type_checking_usage(empty_reason)


def test_audit_falls_back_to_regex_for_unparseable_source() -> None:
    """A file with a syntax error cannot smuggle the pattern past the audit."""
    source = f"def broken(\nif {_BANNED}:\n"

    violations = audit_type_checking_usage(source)

    assert any(message.startswith("line 2:") for message in violations)


def test_check_scans_src_and_tests_roots(tmp_path: Path) -> None:
    """Violations in both scanned roots are reported with relative-path prefixes."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    _ = (tmp_path / "src" / "bad.py").write_text(_IMPORT_FORM, encoding="utf-8")
    _ = (tmp_path / "tests" / "bad.py").write_text(_BLOCK_FORM, encoding="utf-8")

    violations = check_type_checking_ban(tmp_path)

    assert len(violations) == 2
    assert violations[0].startswith("src/bad.py:line 1:")
    assert violations[1].startswith("tests/bad.py:line 1:")


def test_check_passes_for_clean_and_missing_roots(tmp_path: Path) -> None:
    """Clean sources pass, and absent roots degrade to a no-op."""
    (tmp_path / "src").mkdir()
    _ = (tmp_path / "src" / "good.py").write_text(_CLEAN_SOURCE, encoding="utf-8")

    assert check_type_checking_ban(tmp_path) == []


def test_check_skips_unreadable_paths(tmp_path: Path) -> None:
    """An unreadable ``*.py`` path is skipped instead of raising."""
    (tmp_path / "src").mkdir()
    # AI: A directory named like a module reproduces the OSError read path
    # without depending on filesystem permission semantics.
    (tmp_path / "src" / "unreadable.py").mkdir()

    assert check_type_checking_ban(tmp_path) == []


def test_check_current_repository_is_clean() -> None:
    """Baseline: the repository itself has zero non-allowlisted violations."""
    project_root = Path(__file__).resolve().parents[2]

    assert check_type_checking_ban(project_root) == []


def test_quality_result_fails_when_violation_present() -> None:
    """The quality gate as a whole fails and surfaces the labelled message."""
    result = build_quality_check_result(
        _passing_lint(), [], [], [], ["src/bad.py:line 1: banned"]
    )

    assert result.success is False
    assert any("TYPE_CHECKING ban violation" in error for error in result.errors)
    assert "TYPE_CHECKING ban violations:" in result.output


def test_quality_result_passes_without_violations() -> None:
    """With no audit findings the quality result stays successful."""
    result = build_quality_check_result(_passing_lint(), [], [], [], [])

    assert result.success is True
    assert result.errors == []
