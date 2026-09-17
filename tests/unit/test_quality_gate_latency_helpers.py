"""Tests for quality gate latency / response-size helpers (plan: reduce QG tokens).

Plan Step 7: full-tree ``run_quality_gate`` (MCP) verified green on 2026-04-03; field
latency/token success criteria remain for the next measurement window.
"""

from __future__ import annotations

import json

from cortex.core.models import ModelDict
from cortex.tools.execution.pre_commit_process import poll_interval_for_elapsed
from cortex.tools.execution.pre_commit_zero_arg_tools import (
    trim_passing_quality_gate_result,
)


class TestPollIntervalAdaptive:
    def test_fast_window_uses_one_second(self) -> None:
        assert poll_interval_for_elapsed(0.0) == 1.0
        assert poll_interval_for_elapsed(29.9) == 1.0

    def test_after_thirty_seconds_uses_three_seconds(self) -> None:
        assert poll_interval_for_elapsed(30.0) == 3.0
        assert poll_interval_for_elapsed(100.0) == 3.0


class TestTrimPassingResult:
    def test_keeps_summary_fields_drops_heavy_keys(self) -> None:
        result: ModelDict = {
            "status": "success",
            "preflight_passed": True,
            "checks_performed": ["format", "tests"],
            "markdown_result": {"status": "success"},
            "results": {"tests": {"success": True}},
            "checks": [{"name": "x", "status": "passed", "output": "huge" * 1000}],
            "agent_log": "## log",
        }
        out = trim_passing_quality_gate_result(result)
        assert out is result
        assert "results" not in result
        assert "checks" not in result
        assert "agent_log" not in result
        assert result["checks_performed"] == ["format", "tests"]
        assert result["preflight_passed"] is True

    def test_preserves_reflection_when_present(self) -> None:
        result: ModelDict = {
            "preflight_passed": True,
            "status": "success",
            "reflection_result": {"findings": []},
            "results": {},
        }
        _ = trim_passing_quality_gate_result(result)
        assert "reflection_result" in result
        assert "results" not in result

    def test_trimmed_json_under_mcp_token_budget_heuristic(self) -> None:
        """Passing-run trim should drop heavy keys so serialized size stays < ~800 tokens."""
        result: ModelDict = {
            "status": "success",
            "preflight_passed": True,
            "checks_performed": ["format", "tests"],
            "markdown_result": {"status": "success"},
            "summary": "ok",
            "results": {"tests": {"blob": "x" * 20_000}},
            "checks": [{"name": "t", "status": "passed", "output": "y" * 40_000}],
        }
        _ = trim_passing_quality_gate_result(result)
        estimated_tokens = max(1, len(json.dumps(result)) // 4)
        assert estimated_tokens < 800
