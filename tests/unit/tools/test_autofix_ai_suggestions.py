"""Tests for autofix `# AI:` placement suggestions."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cortex.core.models import ModelDict
from cortex.tools.execution.autofix_ai_suggestions import (
    collect_autofix_ai_comment_suggestions,
)


def test_collect_suggestion_for_new_public_def_without_ai_comment() -> None:
    diff = """diff --git a/m.py b/m.py
--- a/m.py
+++ b/m.py
@@ -0,0 +1,2 @@
+def visible():
+    pass
"""
    sugs = collect_autofix_ai_comment_suggestions(diff)
    assert len(sugs) >= 1
    assert any("visible" in s["message"] for s in sugs)


def test_no_suggestion_for_private_def() -> None:
    diff = """diff --git a/m.py b/m.py
--- a/m.py
+++ b/m.py
@@ -0,0 +1,2 @@
+def _hidden():
+    pass
"""
    assert collect_autofix_ai_comment_suggestions(diff) == []


def test_no_suggestion_when_ai_comment_above() -> None:
    diff = """diff --git a/m.py b/m.py
--- a/m.py
+++ b/m.py
@@ -0,0 +1,3 @@
+# AI: explains why this exists
+def visible():
+    pass
"""
    assert collect_autofix_ai_comment_suggestions(diff) == []


_MOD = "cortex.tools.execution.pre_commit_fix_quality"


def _autofix_envelope() -> ModelDict:
    return cast(
        ModelDict,
        {
            "version": 1,
            "status": "completed",
            "result": {
                "results": {
                    "fix_errors": {"errors": [], "warnings": [], "files_modified": []},
                    "format": {"files_formatted": 0},
                    "type_check": {"errors": [], "warnings": []},
                },
                "files_modified": [],
            },
        },
    )


def _suggestion_diff() -> str:
    return """diff --git a/m.py b/m.py
--- a/m.py
+++ b/m.py
@@ -0,0 +1,2 @@
+def visible():
+    pass
"""


def test_worker_finalization_merges_suggestions_from_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.execution.pre_commit_fix_quality import finalize_autofix_result

    envelope = _autofix_envelope()
    diff = _suggestion_diff()

    def _fake_collect(_root: Path) -> str:
        return diff

    monkeypatch.setattr(f"{_MOD}.collect_git_diff_text", _fake_collect)
    with (
        patch(f"{_MOD}.get_tracked_git_changes", return_value=set()),
        patch(f"{_MOD}._run_synapse_formatter_autofix", return_value=None),
        patch(f"{_MOD}._apply_memory_bank_lint_autofix", return_value=[]),
    ):
        data = finalize_autofix_result(tmp_path, envelope, set())
    assert data["status"] == "success"
    suggestions = cast(list[dict[str, str]], data["suggestions"])
    assert any("visible" in suggestion["message"] for suggestion in suggestions)
