"""Verify the detached Swift gate's optional early Markdown check."""

from argparse import Namespace
from pathlib import Path

import pytest

from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.tools.execution import pre_commit_pipeline as pipeline
from cortex.tools.execution import pre_commit_worker as worker
from cortex.tools.execution.pre_commit_helpers_models import CheckStats, PreCommitCheck


class MarkdownScenario:
    """Capture check execution order for a detached worker case."""

    def __init__(self, root: Path, language: str, early: str, final: str) -> None:
        self.root = root
        self.language = language
        self.early = early
        self.final = final
        self.events: list[str] = []

    def non_test(self, *_args: object, **_kwargs: object) -> None:
        self.events.append("non-test")

    def tests(self, *_args: object, **_kwargs: object) -> None:
        self.events.append("tests")

    def markdown(self, _root: str) -> dict[str, object]:
        status = self.final if "tests" in self.events else self.early
        self.events.append("markdown")
        return {"status": status, "files_with_errors": 0}

    def run_checks(self, *_args: object, **kwargs: object) -> dict[str, object]:
        selected = kwargs.get("test_filter")
        pipeline.run_checks_pipeline(
            SwiftAdapter(str(self.root)),
            self.language,
            [PreCommitCheck.TESTS],
            False,
            10,
            0.90,
            None,
            {},
            CheckStats(
                total_errors=0,
                total_warnings=0,
                files_modified=[],
                checks_performed=[],
            ),
            test_filter=selected if isinstance(selected, str) else None,
        )
        return {"status": "success", "success": True, "checks_performed": ["quality"]}

    def attach(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pipeline, "_run_non_test_phase", self.non_test)
        monkeypatch.setattr(pipeline, "_run_tests_phase", self.tests)
        monkeypatch.setattr(worker, "run_markdown_lint", self.markdown)
        monkeypatch.setattr(worker, "_run_checks", self.run_checks)


def _check_args(tmp_path: Path) -> Namespace:
    return Namespace(
        project_root=str(tmp_path),
        checks=["quality", "tests"],
        strict=False,
        timeout=10,
        coverage_threshold=0.90,
        include_markdown_lint=True,
    )


@pytest.mark.parametrize(
    ("language", "quality_gate", "test_filter", "early", "final", "expected_order"),
    [
        ("swift", True, None, "error", "error", ["non-test", "markdown"]),
        (
            "swift",
            True,
            None,
            "success",
            "success",
            ["non-test", "markdown", "tests", "markdown"],
        ),
        (
            "swift",
            True,
            None,
            "success",
            "error",
            ["non-test", "markdown", "tests", "markdown"],
        ),
        ("swift", False, None, "error", "error", ["non-test", "tests", "markdown"]),
        ("swift", True, "testFoo", "error", "error", ["non-test", "tests", "markdown"]),
        ("python", True, None, "error", "error", ["non-test", "tests", "markdown"]),
    ],
)
def test_worker_markdown_order_and_blocked_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    quality_gate: bool,
    test_filter: str | None,
    early: str,
    final: str,
    expected_order: list[str],
) -> None:
    """A clean early check never hides a subsequent Markdown failure."""
    scenario = MarkdownScenario(tmp_path, language, early, final)
    scenario.attach(monkeypatch)
    result, md = (
        worker._run_checks_with_markdown(  # pyright: ignore[reportPrivateUsage]
            _check_args(tmp_path), quality_gate, test_filter
        )
    )
    assert scenario.events == expected_order
    assert md == {"status": final, "files_with_errors": 0}
    assert result["checks_performed"] == ["quality"]
    if "tests" not in scenario.events:
        assert result["status"] == "error"
        assert result["success"] is False
        assert result["full_suite_validated"] is False
        assert result["tests_not_run_reason"] == "markdown_preflight_failed"
    else:
        assert "tests_not_run_reason" not in result
