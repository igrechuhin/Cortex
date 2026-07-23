"""Tests for propose_framework_optimization self-test validation."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.optimization.propose_framework_optimization_selftest import (
    run_self_test,
    self_test_one_file,
)

_VALID_MDC = "---\ndescription: Test rule\nalwaysApply: false\n---\n\nBody text.\n"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    _ = path.write_text(content, encoding="utf-8")
    return path


def test_valid_json_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, "manifest.json", '{"version": "1.0", "categories": {}}')

    assert self_test_one_file(path) is None


def test_invalid_json_fails(tmp_path: Path) -> None:
    path = _write(tmp_path, "manifest.json", "{not-json}")

    reason = self_test_one_file(path)

    assert reason is not None
    assert "invalid JSON" in reason


def test_json_root_must_be_object(tmp_path: Path) -> None:
    path = _write(tmp_path, "manifest.json", "[1, 2, 3]")

    reason = self_test_one_file(path)

    assert reason is not None
    assert "JSON root must be an object" in reason


def test_valid_mdc_frontmatter_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, "rule.mdc", _VALID_MDC)

    assert self_test_one_file(path) is None


def test_mdc_missing_frontmatter_fails(tmp_path: Path) -> None:
    path = _write(tmp_path, "rule.mdc", "no frontmatter here")

    reason = self_test_one_file(path)

    assert reason is not None
    assert "missing YAML frontmatter" in reason


def test_mdc_malformed_frontmatter_yaml_fails(tmp_path: Path) -> None:
    malformed = "---\ndescription: [unterminated\n---\n\nBody\n"
    path = _write(tmp_path, "rule.mdc", malformed)

    reason = self_test_one_file(path)

    assert reason is not None
    assert "malformed frontmatter YAML" in reason


def test_mdc_frontmatter_without_description_fails(tmp_path: Path) -> None:
    content = "---\nalwaysApply: false\n---\n\nBody\n"
    path = _write(tmp_path, "rule.mdc", content)

    reason = self_test_one_file(path)

    assert reason is not None
    assert "non-empty description" in reason


def test_md_without_frontmatter_is_allowed(tmp_path: Path) -> None:
    path = _write(tmp_path, "prompt.md", "# Just a prompt body\n")

    assert self_test_one_file(path) is None


def test_md_with_valid_frontmatter_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, "prompt.md", _VALID_MDC)

    assert self_test_one_file(path) is None


def test_file_exceeding_line_limit_fails(tmp_path: Path) -> None:
    content = "\n".join(f"line {i}" for i in range(500))
    path = _write(tmp_path, "notes.txt", content)

    reason = self_test_one_file(path)

    assert reason is not None
    assert "exceeds" in reason


def test_run_self_test_returns_first_failure(tmp_path: Path) -> None:
    good = _write(tmp_path, "good.mdc", _VALID_MDC)
    bad = _write(tmp_path, "bad.mdc", "no frontmatter")

    reason = run_self_test([good, bad])

    assert reason is not None
    assert "bad.mdc" in reason


def test_run_self_test_all_pass_returns_none(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.mdc", _VALID_MDC)
    b = _write(tmp_path, "b.json", '{"ok": true}')

    assert run_self_test([a, b]) is None
