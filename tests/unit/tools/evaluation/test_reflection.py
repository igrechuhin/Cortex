"""Unit tests for heuristic reflection pass."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from cortex.core.models import ModelDict
from cortex.tools.evaluation.reflection import (
    CritiqueSeverity,
    ReflectionResult,
    analyze_diff,
    apply_reflection_to_gate_result,
    collect_git_diff_text,
)
from cortex.tools.reflection_constants import (
    REFLECTION_CHECKLIST_MARKDOWN,
    build_reflection_checklist_markdown,
    detect_languages_in_diff,
)


def test_analyze_diff_clean() -> None:
    rr = analyze_diff(
        "+++ b/x.py\n+def ok():\n+    return 1\n",
        "{}",
        REFLECTION_CHECKLIST_MARKDOWN,
    )
    assert rr.approved
    assert rr.score == 100
    assert rr.items == []


def test_try_without_except_is_error() -> None:
    diff = """
+++ b/x.py
@@
+def f():
+    try:
+        pass
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not rr.approved
    assert any(i.severity == CritiqueSeverity.ERROR for i in rr.items)


def test_todo_is_warning_only() -> None:
    diff = "+# TODO: revisit"
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert rr.approved
    assert any("TODO" in i.description for i in rr.items)


def test_secret_like_literal_error() -> None:
    diff = '+password = "secret123"'
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not rr.approved
    assert any(i.category.value == "security" for i in rr.items)


def test_apply_reflection_fails_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from cortex.tools.evaluation import reflection as R

    def _fake_collect(_root: Path) -> str:
        return "+++ b/bad.py\n+try:\n    pass\n"

    monkeypatch.setattr(R, "collect_git_diff_text", _fake_collect)
    result: ModelDict = cast(ModelDict, {"preflight_passed": True})
    apply_reflection_to_gate_result(
        Path("/tmp"),
        result,
        {"reflection": True},
    )
    assert result["preflight_passed"] is False
    assert result.get("reflection_languages") == ["python"]
    raw = result.get("reflection_result")
    assert isinstance(raw, dict)
    rr = ReflectionResult.model_validate(raw)
    assert not rr.approved


def test_apply_reflection_skipped_when_disabled() -> None:
    result: ModelDict = cast(ModelDict, {"preflight_passed": True})
    apply_reflection_to_gate_result(Path("/tmp"), result, {"reflection": False})
    assert result.get("reflection_result") is None
    assert result["preflight_passed"] is True


def test_collect_git_diff_text_non_repo_returns_empty(tmp_path: Path) -> None:
    assert collect_git_diff_text(tmp_path) == ""


def test_collect_git_diff_git_failure_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocked = MagicMock(returncode=1, stdout=b"diff")
    monkeypatch.setattr(
        "cortex.tools.evaluation.reflection.subprocess.run",
        MagicMock(return_value=mocked),
    )
    assert collect_git_diff_text(Path("/tmp")) == ""


def test_collect_git_diff_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    mocked = MagicMock(returncode=0, stdout=b"x" * 200)
    monkeypatch.setattr(
        "cortex.tools.evaluation.reflection.subprocess.run",
        MagicMock(return_value=mocked),
    )
    out = collect_git_diff_text(Path("/tmp"), max_bytes=50)
    assert "truncated for reflection" in out


def test_belief_stale_warning_when_context_belief_and_other_edits() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,3 +1,4 @@
 # BELIEF: invariant
 def f():
+    y = 2
     return 1
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert rr.approved
    assert any("BELIEF" in i.description for i in rr.items)


def test_belief_updated_pair_no_stale_warning() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,2 +1,2 @@
-# BELIEF: old
+# BELIEF: new
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not any("BELIEF" in i.description for i in rr.items)


def test_risky_dict_access_warns_to_add_belief() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,2 +1,3 @@
 def f(payload):
+    return payload["user"]
 """
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    matches = [i for i in rr.items if "raw dict key access" in i.description]
    assert len(matches) == 1
    assert matches[0].severity == CritiqueSeverity.WARNING
    assert "BELIEF" in matches[0].suggestion


def test_risky_chained_attribute_access_warns_to_add_belief() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,2 +1,3 @@
 def f(response):
+    return response.data.user.name
 """
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    matches = [i for i in rr.items if "chained attribute access" in i.description]
    assert len(matches) == 1
    assert matches[0].severity == CritiqueSeverity.WARNING
    assert "BELIEF" in matches[0].suggestion


def test_risky_mid_function_access_skips_typed_dict_bindings() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,4 +1,5 @@
+class UserPayload(TypedDict):
+    user: str
 def f(payload: UserPayload):
+    return payload["user"]
 """
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not any("raw dict key access" in i.description for i in rr.items)


def test_single_attribute_access_does_not_trigger_belief_warning() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,2 +1,3 @@
 def f(obj):
+    return obj.value
 """
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not any("attribute access" in i.description for i in rr.items)


def test_non_python_diff_skips_risky_mid_function_warning() -> None:
    diff = """diff --git a/src/x.ts b/src/x.ts
--- a/src/x.ts
+++ b/src/x.ts
@@ -1,2 +1,3 @@
 function f(payload: object) {
+  return payload["user"];
 }
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not any("raw dict key access" in i.description for i in rr.items)


def test_risky_dict_access_deduplicates_per_file() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,2 +1,4 @@
 def f(payload):
+    user = payload["user"]
+    email = payload["email"]
 """
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    matches = [i for i in rr.items if "raw dict key access" in i.description]
    assert len(matches) == 1


def test_untested_public_under_src_warning() -> None:
    diff = """+++ b/src/mod.py
@@
+def new_fn():
+    pass
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert rr.approved
    assert any(i.category.value == "test_coverage" for i in rr.items)


def test_apply_reflection_skips_when_preflight_false() -> None:
    result: ModelDict = cast(ModelDict, {"preflight_passed": False})
    apply_reflection_to_gate_result(
        Path("/tmp"),
        result,
        {"reflection": True},
    )
    assert "reflection_result" not in result


def test_try_with_except_avoids_logic_error() -> None:
    diff = """+++ b/m.py
+try:
+    pass
+except Exception:
+    pass
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not any(
        i.category.value == "logic" and i.severity == CritiqueSeverity.ERROR
        for i in rr.items
    )


def test_untested_skipped_when_tests_path_in_diff() -> None:
    diff = """+++ b/src/a.py
+def f():
+    pass
+++ b/tests/test_a.py
+def test_f():
+    pass
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not any(i.category.value == "test_coverage" for i in rr.items)


def test_collect_git_diff_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cortex.tools.evaluation.reflection.subprocess.run",
        MagicMock(side_effect=FileNotFoundError()),
    )
    assert collect_git_diff_text(Path("/tmp")) == ""


def test_collect_git_diff_small_output_no_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocked = MagicMock(returncode=0, stdout=b"small-diff")
    monkeypatch.setattr(
        "cortex.tools.evaluation.reflection.subprocess.run",
        MagicMock(return_value=mocked),
    )
    assert collect_git_diff_text(Path("/tmp")) == "small-diff"


def test_apply_reflection_session_config_enables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cortex.tools.evaluation import reflection as R

    def _fake_clean(_root: Path) -> str:
        return "+# clean\n"

    def _fake_session() -> dict[str, object]:
        return {"force_reflection": True}

    monkeypatch.setattr(R, "collect_git_diff_text", _fake_clean)
    monkeypatch.setattr(
        "cortex.tools.evaluation.reflection.read_session_config",
        _fake_session,
    )
    result: ModelDict = cast(ModelDict, {"preflight_passed": True})
    apply_reflection_to_gate_result(
        Path("/tmp"),
        result,
        {"reflection": False, "force_reflection": False},
    )
    assert "reflection_result" in result
    assert result.get("reflection_languages") == []
    assert result["preflight_passed"] is True


def test_detect_languages_from_paths() -> None:
    diff = """+++ b/lib/Foo.swift
+x
+++ b/pkg/handler.go
+y
"""
    assert detect_languages_in_diff(diff) == ["swift", "go"]


def test_detect_languages_from_diff_git_line_only() -> None:
    diff = "diff --git a/internal/app.go b/internal/app.go\n"
    assert detect_languages_in_diff(diff) == ["go"]


def test_build_checklist_general_only() -> None:
    text = build_reflection_checklist_markdown([])
    assert "### Python" not in text
    assert "Reflection Checklist" in text


def test_build_checklist_python_only() -> None:
    text = build_reflection_checklist_markdown(["python"])
    assert "### Python" in text
    assert "### Swift" not in text


def test_non_python_diff_skips_python_try_heuristic() -> None:
    diff = """+++ b/README.md
+Example: try: not python syntax discussion
+try:
"""
    rr = analyze_diff(diff, "{}", REFLECTION_CHECKLIST_MARKDOWN)
    assert not any(
        i.category.value == "logic" and i.severity == CritiqueSeverity.ERROR
        for i in rr.items
    )
