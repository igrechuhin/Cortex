"""Selected-test receipts cannot certify or reuse a different quality-gate scope."""

import argparse
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.execution_env import LocalExecutionEnvironment
from cortex.core.models import ModelDict
from cortex.services.framework_adapters.base import CheckResult
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.tools.execution import pre_commit_quality_gate_job as jobs
from cortex.tools.execution import pre_commit_worker as worker
from cortex.tools.execution import pre_commit_zero_arg_tools as gate
from cortex.tools.execution.pre_commit_detached import compute_args_hash
from cortex.tools.execution.pre_commit_dirty_state import PipelineDirtyTracker
from cortex.tools.execution.pre_commit_helpers_models import CheckStats, PreCommitCheck
from cortex.tools.execution.pre_commit_pipeline import run_checks_pipeline
from cortex.tools.execution.pre_commit_pipeline_processors import process_tests_check
from cortex.tools.execution.pre_commit_process import build_worker_cmd
from cortex.tools.execution.pre_commit_quality_gate_job import quality_gate_job_path
from cortex.tools.execution.pre_commit_test_scope import (
    describe_test_scope,
    validate_test_filter,
)
from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


@pytest.mark.parametrize("value", ["", " ", 1, False, [], "x\ny", "x" * 4097])
def test_invalid_gate_filter_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="test_filter"):
        _ = validate_test_filter(value)


def test_absent_filter_retains_full_suite_receipt() -> None:
    result: ModelDict = {"success": True}
    assert validate_test_filter(None) is None
    describe_test_scope(result, None)
    assert result == {"success": True}


def test_filter_changes_job_identity_and_path(tmp_path: Path) -> None:
    hashes = {
        compute_args_hash(["tests"], 900, 0.9, False, True, selection)
        for selection in (None, "feature_a", "feature_b")
    }
    paths = {
        quality_gate_job_path(tmp_path, 900, 0.9, selection)
        for selection in (None, "feature_a", "feature_b")
    }
    assert len(hashes) == len(paths) == 3


def test_filter_is_one_worker_argument(tmp_path: Path) -> None:
    expression = "feature and not slow; literal"
    command = build_worker_cmd(
        tmp_path, tmp_path / "result.json", ["tests"], 900, 0.9, False, True, expression
    )
    assert command[-1] == f"--test-filter={expression}"
    assert command.count(command[-1]) == 1
    assert "--include-markdown-lint" in command


def _run_worker(tmp_path: Path, selection: str | None) -> dict[str, object]:
    """Exercise the public detached-worker entrypoint without filesystem side effects."""
    args = argparse.Namespace(
        project_root=str(tmp_path),
        checks=["quality", "tests"],
        timeout=900,
        coverage_threshold=0.9,
        strict=False,
        test_filter=selection,
        include_markdown_lint=True,
        quality_gate=True,
        result_file=str(tmp_path / "result.json"),
    )
    with (
        patch.object(worker, "_parse_worker_args", return_value=args),
        patch.object(worker, "write_status"),
        patch.object(worker, "_maybe_write_early_exit", return_value=False),
        patch.object(worker, "_run_markdown_lint", return_value={}),
        patch.object(worker, "_write_success_result") as write,
    ):
        worker.main()
    result: dict[str, object] = write.call_args.args[3]
    return result


def test_worker_receipt_never_skips_scoped_checks_from_global_fingerprint(
    tmp_path: Path,
) -> None:
    adapter = PythonAdapter(str(tmp_path))
    language = MagicMock(language="python")
    with (
        patch.object(
            worker, "resolve_adapter_worker", return_value=(adapter, language)
        ),
        patch.object(worker, "_run_checks_core", return_value={"success": True}) as run,
        patch(
            "cortex.tools.execution.pre_commit_dirty_state.partition_skippable_checks"
        ) as partition,
    ):
        result = _run_worker(tmp_path, "feature_a")
    partition.assert_not_called()
    assert run.call_args.kwargs["test_filter"] == "feature_a"
    assert run.call_args.args[2] == ["quality", "tests"]
    assert result["test_scope"] == "selected_tests"
    assert result["full_suite_validated"] is False


def test_worker_default_keeps_fingerprint_skipping(tmp_path: Path) -> None:
    with patch(
        "cortex.tools.execution.pre_commit_dirty_state.partition_skippable_checks",
        return_value=([], {"tests": "unchanged"}),
    ) as partition:
        result = _run_worker(tmp_path, None)
    partition.assert_called_once_with(tmp_path, ["quality", "tests"])
    assert result["skipped_checks"] == ["tests"]


def test_worker_cli_passes_filter_to_execution(tmp_path: Path) -> None:
    with (patch.object(worker, "_run_checks", return_value={}) as run,):
        _ = _run_worker(tmp_path, "feature_a")
    assert run.call_args.kwargs["test_filter"] == "feature_a"


def test_unknown_adapter_rejects_selection() -> None:
    with pytest.raises(ValueError, match="Python pytest and SwiftPM"):
        process_tests_check(
            MagicMock(),
            [PreCommitCheck.TESTS],
            900,
            0.9,
            {},
            CheckStats(total_errors=0, total_warnings=0),
            test_filter="feature",
        )


def _patch_selected_pipeline(
    stack: ExitStack, adapter: PythonAdapter, passed: CheckResult
) -> tuple[MagicMock, MagicMock, MagicMock, list[MagicMock]]:
    """Patch selected-source wiring and every non-test pipeline processor."""
    module = "cortex.tools.execution.pre_commit_pipeline"
    readonly = stack.enter_context(
        patch(f"{module}.selected_source_checks", return_value=(passed, passed))
    )
    fix = stack.enter_context(patch.object(adapter, "fix_errors"))
    formatting = stack.enter_context(patch.object(adapter, "format_code"))
    remaining = [
        stack.enter_context(patch(f"{module}.{name}"))
        for name in (
            "process_quality_check",
            "process_synapse_format_check",
            "process_synapse_lint_check",
            "process_script_based_checks",
            "process_type_check",
            "process_tests_check",
        )
    ]
    return readonly, fix, formatting, remaining


def test_selected_pipeline_keeps_non_test_checks_without_mutations(
    tmp_path: Path,
) -> None:
    adapter = PythonAdapter(str(tmp_path))
    stats = CheckStats(total_errors=0, total_warnings=0)
    passed = CheckResult(check_type="lint", success=True, output="")
    with ExitStack() as stack:
        readonly, fix, formatting, remaining = _patch_selected_pipeline(
            stack, adapter, passed
        )
        run_checks_pipeline(
            adapter,
            "python",
            list(PreCommitCheck),
            False,
            900,
            0.9,
            None,
            {},
            stats,
            test_filter="feature",
        )
    readonly.assert_called_once_with(adapter)
    fix.assert_not_called()
    formatting.assert_not_called()
    assert all(mock.call_count == 1 for mock in remaining)
    assert stats.checks_performed == ["fix_errors", "format"]
    assert remaining[-1].call_args.kwargs["test_filter"] == "feature"


@pytest.mark.asyncio
async def test_gate_rejects_invalid_selection_before_spawning(tmp_path: Path) -> None:
    with (
        patch.object(gate, "get_current_project_root", return_value=tmp_path),
        patch.object(
            gate,
            "_read_quality_gate_config",
            return_value=(900, 0.9, True, {"test_filter": ""}),
        ),
        patch.object(gate, "_spawn_and_poll_phase_a", new_callable=AsyncMock) as spawn,
    ):
        result = await gate.run_quality_gate_inner(None, LocalExecutionEnvironment())
    assert result["status"] == "error"
    spawn.assert_not_called()


@pytest.mark.asyncio
async def test_real_session_filter_reaches_spawn_without_relabeling_busy_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    written = json.loads(
        await pipeline_handoff(
            operation="write_task",
            pipeline="commit",
            phase="checks",
            data={"test_filter": "feature_b"},
        )
    )
    assert written["status"] == "ok"
    active: ModelDict = {
        "status": "running",
        "job_id": "other",
        "test_filter": "feature_a",
    }
    with (
        patch.object(gate, "get_current_project_root", return_value=tmp_path),
        patch.object(
            gate, "_spawn_and_poll_phase_a", new_callable=AsyncMock, return_value=active
        ) as spawn,
    ):
        result = await gate.run_quality_gate_inner(None, LocalExecutionEnvironment())
    assert spawn.call_args.kwargs["test_filter"] == "feature_b"
    assert result["test_filter"] == "feature_a"


@pytest.mark.asyncio
async def test_bounded_gate_returns_other_active_job_without_scope_relabeling(
    tmp_path: Path,
) -> None:
    active_path = quality_gate_job_path(tmp_path, 900, 0.9, "feature_a")
    active: ModelDict = {
        "status": "running",
        "result_file": str(active_path),
        "job_id": active_path.stem,
        "preflight_passed": False,
    }
    with (
        patch.object(jobs, "find_running_job", return_value=active),
        patch.object(gate, "start_phase_a_job") as spawn,
    ):
        result = await jobs.run_bounded_phase_a(
            tmp_path,
            900,
            0.9,
            True,
            None,
            LocalExecutionEnvironment(),
            1.0,
            test_filter="feature_b",
        )
    assert result == active
    assert "test_filter" not in result
    assert "test_scope" not in result
    spawn.assert_not_called()


def _patch_scoped_gate(
    stack: ExitStack, tmp_path: Path, result: ModelDict
) -> MagicMock:
    """Patch gate persistence and spawning for one selected-test run."""
    tracker = stack.enter_context(patch.object(PipelineDirtyTracker, "get_instance"))
    _ = stack.enter_context(patch.object(gate, "apply_reflection_to_gate_result"))
    for name in (
        "persist_gate_feedback",
        "record_gate_result",
        "append_log_entry_best_effort",
    ):
        _ = stack.enter_context(patch.object(gate, name, new_callable=AsyncMock))
    _ = stack.enter_context(
        patch.object(gate, "get_current_project_root", return_value=tmp_path)
    )
    _ = stack.enter_context(
        patch.object(
            gate,
            "_read_quality_gate_config",
            return_value=(900, 0.9, True, {"test_filter": "feature"}),
        )
    )
    _ = stack.enter_context(
        patch.object(
            gate,
            "_spawn_and_poll_phase_a",
            new_callable=AsyncMock,
            return_value=result,
        )
    )
    return tracker


@pytest.mark.asyncio
async def test_scoped_pass_does_not_publish_full_suite_fingerprint(
    tmp_path: Path,
) -> None:
    result: ModelDict = {"preflight_passed": True, "success": True}
    describe_test_scope(result, "feature")
    with ExitStack() as stack:
        tracker = _patch_scoped_gate(stack, tmp_path, result)
        result = await gate.run_quality_gate_inner(None, LocalExecutionEnvironment())
    tracker.return_value.record_phase_a.assert_called_once_with(tmp_path, False)
    assert result["full_suite_validated"] is False
    assert result["coverage_scope"] == "selected_tests_only"
