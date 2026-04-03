"""Tests for autofix `# AI:` placement suggestions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

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
_STARTED = {"job_id": "x", "status": "started"}


@pytest.mark.asyncio
async def test_autofix_impl_merges_suggestions_from_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.execution.pre_commit_fix_quality import autofix_impl

    envelope = cast(
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
    diff = """diff --git a/m.py b/m.py
--- a/m.py
+++ b/m.py
@@ -0,0 +1,2 @@
+def visible():
+    pass
"""

    def _fake_collect(_root: Path) -> str:
        return diff

    monkeypatch.setattr(f"{_MOD}.collect_git_diff_text", _fake_collect)
    with (
        patch(f"{_MOD}.start_fix_job_impl", return_value=_STARTED),
        patch(f"{_MOD}.poll_for_result", new_callable=AsyncMock, return_value=envelope),
    ):
        out = await autofix_impl(tmp_path, include_untracked_markdown=True, ctx=None)
    data = json.loads(out)
    assert data["status"] == "success"
    assert data.get("suggestions")
    assert any("visible" in str(s.get("message", "")) for s in data["suggestions"])
