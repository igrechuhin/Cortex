"""Tests for Phase 57 extension: model benchmark and comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.model_benchmark import (
    ModelBenchmarkComparison,
    ModelBenchmarkRecord,
    benchmark_model,
)


def test_model_benchmark_record_execution_pass_rate() -> None:
    """ModelBenchmarkRecord execution_pass_rate is computed from passed/total_run."""
    record = ModelBenchmarkRecord(
        model_name="m",
        generated_at="2026-01-01T00:00:00Z",
        overall_success_rate=0.9,
        execution_passed=4,
        execution_failed=1,
        execution_skipped=0,
        execution_total_run=5,
        execution_pass_rate=0.8,
        tasks_loaded=5,
        analysis={},
        execution_summary={},
    )
    assert record.execution_pass_rate == 0.8


def test_model_benchmark_comparison_fields() -> None:
    """ModelBenchmarkComparison has baseline_model, current_model, deltas, regressions, improvements."""
    comp = ModelBenchmarkComparison(
        baseline_model="base",
        baseline_generated_at="2026-01-01T00:00:00Z",
        current_model="new",
        current_generated_at="2026-01-02T00:00:00Z",
        success_rate_delta=0.05,
        execution_pass_rate_delta=0.1,
        regressions=["t1"],
        improvements=["t2"],
    )
    assert comp.baseline_model == "base"
    assert comp.current_model == "new"
    assert comp.success_rate_delta == 0.05
    assert comp.regressions == ["t1"]
    assert comp.improvements == ["t2"]


@pytest.mark.asyncio
async def test_benchmark_model_stores_and_returns_payload(tmp_path: Path) -> None:
    """benchmark_model runs full eval (mocked), stores result, returns JSON."""
    fake_payload: dict[str, object] = {
        "tasks_loaded": 2,
        "generated_at": "2026-02-24T10:00:00Z",
        "analysis": {"overall_success_rate": 0.9},
        "execution_summary": {
            "execution_passed": 2,
            "execution_failed": 0,
            "execution_skipped": 0,
            "execution_total_run": 2,
            "results": [],
        },
    }
    with (
        patch(
            "cortex.tools.model_benchmark.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.model_benchmark._run_full_eval",
            new_callable=AsyncMock,
            return_value=fake_payload,
        ),
    ):
        result_str = await benchmark_model("test-model")
    result = json.loads(result_str)
    assert result["status"] == "success"
    assert result["model_name"] == "test-model"
    assert result["overall_success_rate"] == 0.9
    assert result["history_count"] == 1
    assert "cache_file" in result
    cache_file = tmp_path / ".cortex" / ".cache" / "evals" / "model_benchmarks.json"
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert "benchmarks" in data
    assert len(data["benchmarks"]) == 1
    assert data["benchmarks"][0]["model_name"] == "test-model"


@pytest.mark.asyncio
async def test_benchmark_model_comparison_when_baseline_present(tmp_path: Path) -> None:
    """benchmark_model includes comparison when baseline_model_name matches prior run."""
    fake_payload: dict[str, object] = {
        "tasks_loaded": 2,
        "generated_at": "2026-02-24T11:00:00Z",
        "analysis": {"overall_success_rate": 0.95},
        "execution_summary": {
            "execution_passed": 2,
            "execution_failed": 0,
            "execution_skipped": 0,
            "execution_total_run": 2,
            "results": [
                {
                    "task_id": "t1",
                    "passed": True,
                    "message": "",
                    "duration_ms": 0.0,
                    "skipped": False,
                },
                {
                    "task_id": "t2",
                    "passed": True,
                    "message": "",
                    "duration_ms": 0.0,
                    "skipped": False,
                },
            ],
        },
    }
    cache_dir = tmp_path / ".cortex" / ".cache" / "evals"
    _ = cache_dir.mkdir(parents=True, exist_ok=True)
    baseline_record: dict[str, object] = {
        "model_name": "current",
        "generated_at": "2026-02-24T10:00:00Z",
        "overall_success_rate": 0.9,
        "execution_passed": 1,
        "execution_failed": 1,
        "execution_skipped": 0,
        "execution_total_run": 2,
        "execution_pass_rate": 0.5,
        "tasks_loaded": 2,
        "analysis": {},
        "execution_summary": {
            "results": [
                {
                    "task_id": "t1",
                    "passed": True,
                    "message": "",
                    "duration_ms": 0.0,
                    "skipped": False,
                },
                {
                    "task_id": "t2",
                    "passed": False,
                    "message": "",
                    "duration_ms": 0.0,
                    "skipped": False,
                },
            ]
        },
    }
    _ = (cache_dir / "model_benchmarks.json").write_text(
        json.dumps({"benchmarks": [baseline_record]}, indent=2),
        encoding="utf-8",
    )
    with (
        patch(
            "cortex.tools.model_benchmark.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.model_benchmark._run_full_eval",
            new_callable=AsyncMock,
            return_value=fake_payload,
        ),
    ):
        result_str = await benchmark_model(
            "new-model",
            baseline_model_name="current",
        )
    result = json.loads(result_str)
    assert result["status"] == "success"
    assert "comparison" in result
    comp = cast(dict[str, object], result["comparison"])
    assert comp["baseline_model"] == "current"
    assert comp["current_model"] == "new-model"
    delta = comp.get("success_rate_delta")
    assert isinstance(delta, (int, float)) and abs(delta - 0.05) < 1e-9
    improvements = comp.get("improvements")
    assert isinstance(improvements, list) and "t2" in improvements


@pytest.mark.asyncio
async def test_benchmark_model_comparison_note_when_baseline_missing(
    tmp_path: Path,
) -> None:
    """benchmark_model sets comparison_note when baseline_model_name has no prior run."""
    fake_payload: dict[str, object] = {
        "tasks_loaded": 0,
        "generated_at": "2026-02-24T12:00:00Z",
        "analysis": {},
        "execution_summary": {},
    }
    with (
        patch(
            "cortex.tools.model_benchmark.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.model_benchmark._run_full_eval",
            new_callable=AsyncMock,
            return_value=fake_payload,
        ),
    ):
        result_str = await benchmark_model(
            "only-run",
            baseline_model_name="nonexistent",
        )
    result = json.loads(result_str)
    assert result["comparison"] is None
    assert "comparison_note" in result
    assert "nonexistent" in str(result["comparison_note"])
