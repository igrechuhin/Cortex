"""Tests for the detached fix-quality pipeline.

Covers:
- autofix_impl: success/error/timeout envelopes -> correct JSON
- spawn_detached_fix_worker: result path uses fix prefix
- start_fix_job_impl: always clears prior result and spawns fresh
- build_fix_worker_cmd: correct argv
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.context_logging import MCPContext
from cortex.core.models import ModelDict
from cortex.tools.execution.pre_commit_fix_quality import (
    FixQualityResult,
    parse_fix_envelope,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _completed_envelope(
    results: dict[str, object] | None = None,
    files_modified: list[str] | None = None,
    markdown_result: dict[str, object] | None = None,
) -> ModelDict:
    """Build a completed-status envelope for tests."""
    inner: dict[str, object] = {
        "results": results or {},
        "files_modified": files_modified or [],
    }
    envelope: dict[str, object] = {
        "version": 1,
        "status": "completed",
        "result": inner,
    }
    if markdown_result is not None:
        envelope["markdown_result"] = markdown_result
    return cast(ModelDict, envelope)


def _error_envelope(error: str, status: str = "error") -> ModelDict:
    """Build an error/timeout-status envelope."""
    return cast(
        ModelDict,
        {"version": 1, "status": status, "error": error},
    )


def _full_results_dict(
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    files_modified: list[str] | None = None,
    files_formatted: int = 0,
) -> dict[str, object]:
    """Build the nested results dict inside an envelope."""
    return {
        "fix_errors": {
            "errors": errors or [],
            "warnings": warnings or [],
            "files_modified": files_modified or [],
        },
        "format": {"files_formatted": files_formatted},
        "type_check": {"errors": [], "warnings": []},
    }


_MOD = "cortex.tools.execution.pre_commit_fix_quality"
_STARTED = {"job_id": "abc123", "status": "started"}


async def _run_autofix_impl(
    tmp_path: Path,
    envelope: ModelDict,
    *,
    include_untracked_markdown: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Patch start + poll, then call autofix_impl."""
    with (
        patch(f"{_MOD}.start_fix_job_impl", return_value=_STARTED),
        patch(f"{_MOD}.poll_for_result", new_callable=AsyncMock, return_value=envelope),
    ):
        from cortex.tools.execution.pre_commit_fix_quality import autofix_impl

        return await autofix_impl(
            tmp_path,
            include_untracked_markdown=include_untracked_markdown,
            ctx=ctx,
        )


# ---------------------------------------------------------------------------
# _parse_fix_envelope
# ---------------------------------------------------------------------------


class TestParseFixEnvelope:
    """Unit tests for the envelope parser (no I/O)."""

    def test_success_envelope_returns_valid_json(self) -> None:
        envelope = _completed_envelope(
            results=_full_results_dict(
                errors=["E1"],
                warnings=["W1"],
                files_modified=["a.py"],
                files_formatted=2,
            ),
            files_modified=["a.py"],
            markdown_result={
                "success": True,
                "files_fixed": 1,
                "results": [{"file": "README.md", "fixed": True}],
            },
        )
        out = parse_fix_envelope(envelope)
        result = FixQualityResult(**json.loads(out))
        assert result.status.value == "success"
        assert result.errors_fixed == 1
        assert result.warnings_fixed == 1
        assert result.formatting_issues_fixed == 2
        assert result.markdown_issues_fixed == 1
        assert "a.py" in result.files_modified
        assert "README.md" in result.files_modified

    def test_error_envelope_returns_error_json(self) -> None:
        envelope = _error_envelope("worker crashed")
        data = json.loads(parse_fix_envelope(envelope))
        assert data["status"] == "error"
        assert "error_type" in data

    def test_timeout_envelope_returns_error_json(self) -> None:
        envelope = _error_envelope("Timeout after 960s", status="timeout")
        data = json.loads(parse_fix_envelope(envelope))
        assert data["status"] == "error"

    def test_empty_result_returns_zero_counts(self) -> None:
        envelope = _completed_envelope()
        result = FixQualityResult(**json.loads(parse_fix_envelope(envelope)))
        assert result.status.value == "success"
        assert result.errors_fixed == 0
        assert result.markdown_issues_fixed == 0

    def test_no_markdown_result_is_handled(self) -> None:
        envelope = _completed_envelope(results={}, files_modified=[])
        data = json.loads(parse_fix_envelope(envelope))
        assert data["status"] == "success"
        assert data["markdown_issues_fixed"] == 0

    def test_parse_fix_envelope_override_files_modified(self) -> None:
        envelope = _completed_envelope(
            results=_full_results_dict(),
            files_modified=["noise.md"],
        )
        out = parse_fix_envelope(
            envelope,
            files_modified_override=["actual.py", "actual_test.py"],
        )
        data = json.loads(out)
        assert data["status"] == "success"
        assert data["files_modified"] == ["actual.py", "actual_test.py"]


# ---------------------------------------------------------------------------
# autofix_impl -- detached spawn + poll
# ---------------------------------------------------------------------------


class TestFixQualityIssuesImpl:
    """Tests for autofix_impl using mocked detached worker."""

    @pytest.mark.asyncio
    async def test_success_envelope_returned_from_poll(self, tmp_path: Path) -> None:
        envelope = _completed_envelope(
            results=_full_results_dict(),
            files_modified=[],
        )
        out = await _run_autofix_impl(tmp_path, envelope)
        assert json.loads(out)["status"] == "success"

    @pytest.mark.asyncio
    async def test_error_envelope_surfaced(self, tmp_path: Path) -> None:
        envelope = _error_envelope("ruff not found")
        out = await _run_autofix_impl(
            tmp_path, envelope, include_untracked_markdown=False
        )
        assert json.loads(out)["status"] == "error"

    @pytest.mark.asyncio
    async def test_timeout_envelope_surfaced(self, tmp_path: Path) -> None:
        envelope = _error_envelope("Timeout after 960s", status="timeout")
        out = await _run_autofix_impl(
            tmp_path, envelope, include_untracked_markdown=False
        )
        assert json.loads(out)["status"] == "error"

    @pytest.mark.asyncio
    async def test_poll_called_with_ctx(self, tmp_path: Path) -> None:
        mock_ctx = AsyncMock()
        envelope = _completed_envelope()
        poll_mock = AsyncMock(return_value=envelope)
        with (
            patch(f"{_MOD}.start_fix_job_impl", return_value=_STARTED),
            patch(f"{_MOD}.poll_for_result", poll_mock),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import autofix_impl

            _ = await autofix_impl(
                tmp_path, include_untracked_markdown=True, ctx=mock_ctx
            )
        _, kwargs = poll_mock.call_args
        assert kwargs.get("ctx") is mock_ctx or poll_mock.call_args[0][1] is mock_ctx

    @pytest.mark.asyncio
    async def test_uses_git_delta_for_files_modified(self, tmp_path: Path) -> None:
        envelope = _completed_envelope(
            results=_full_results_dict(), files_modified=["noise.md"]
        )
        git_side = [{"already_dirty.py"}, {"already_dirty.py", "new_fix.py"}]
        with (
            patch(f"{_MOD}.start_fix_job_impl", return_value=_STARTED),
            patch(
                f"{_MOD}.poll_for_result", new_callable=AsyncMock, return_value=envelope
            ),
            patch(f"{_MOD}._get_tracked_git_changes", side_effect=git_side),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import autofix_impl

            out = await autofix_impl(
                tmp_path, include_untracked_markdown=True, ctx=None
            )
        data = json.loads(out)
        assert data["status"] == "success"
        assert data["files_modified"] == ["new_fix.py"]

    @pytest.mark.asyncio
    async def test_records_synapse_formatter_issue_when_fix_fails(
        self, tmp_path: Path
    ) -> None:
        envelope = _completed_envelope(results=_full_results_dict(), files_modified=[])
        with (
            patch(f"{_MOD}.start_fix_job_impl", return_value=_STARTED),
            patch(
                f"{_MOD}.poll_for_result", new_callable=AsyncMock, return_value=envelope
            ),
            patch(
                f"{_MOD}._run_synapse_formatter_autofix",
                return_value="synapse formatter autofix failed for language 'swift': boom",
            ),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import autofix_impl

            out = await autofix_impl(
                tmp_path, include_untracked_markdown=True, ctx=None
            )
        data = json.loads(out)
        assert data["status"] == "success"
        assert data["remaining_issues"] == [
            "synapse formatter autofix failed for language 'swift': boom"
        ]


# ---------------------------------------------------------------------------
# spawn_detached_fix_worker -- result path uses fix prefix
# ---------------------------------------------------------------------------


class TestSpawnDetachedFixWorker:
    """Tests for spawn_detached_fix_worker."""

    def test_result_path_uses_fix_prefix(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_detached import spawn_detached_fix_worker

        with patch(
            "cortex.tools.execution.pre_commit_detached.spawn_detached_process"
        ) as mock_spawn:
            mock_spawn.return_value = None
            rp = spawn_detached_fix_worker(
                tmp_path, include_markdown_fix=False, args_hash="abc123"
            )
        assert "pre_commit_fix_result_" in rp.name
        assert "abc123" in rp.name

    def test_no_fix_prefix_in_read_only_results(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_process import pre_commit_result_path
        from cortex.tools.execution.session_paths import session_dir

        rp = pre_commit_result_path(session_dir(tmp_path), "abc123")
        assert "pre_commit_fix_result_" not in rp.name


# ---------------------------------------------------------------------------
# start_fix_job_impl -- always clears and spawns fresh
# ---------------------------------------------------------------------------


class TestStartFixJobImpl:
    """Tests for start_fix_job_impl."""

    def test_clears_prior_result_before_spawning(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_detached import (
            fix_args_hash,
            fix_result_path,
            start_fix_job_impl,
        )
        from cortex.tools.execution.session_paths import session_dir

        args_hash = fix_args_hash(include_markdown_fix=False)
        rp = fix_result_path(session_dir(tmp_path), args_hash)
        rp.parent.mkdir(parents=True, exist_ok=True)
        _ = rp.write_text('{"status":"completed"}')
        assert rp.exists()
        with patch(
            "cortex.tools.execution.pre_commit_detached.spawn_detached_fix_worker"
        ) as mock_spawn:
            mock_spawn.return_value = rp
            result = start_fix_job_impl(tmp_path, include_markdown_fix=False)
        assert not rp.exists()
        assert result["status"] == "started"

    def test_returns_started_status(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_detached import start_fix_job_impl

        with patch(
            "cortex.tools.execution.pre_commit_detached.spawn_detached_fix_worker"
        ) as mock_spawn:
            mock_spawn.return_value = tmp_path / "result.json"
            result = start_fix_job_impl(tmp_path, include_markdown_fix=True)
        assert result["status"] == "started"
        assert "job_id" in result


# ---------------------------------------------------------------------------
# build_fix_worker_cmd
# ---------------------------------------------------------------------------


class TestBuildFixWorkerCmd:
    """Tests for build_fix_worker_cmd."""

    def test_includes_fix_worker_module(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_process import build_fix_worker_cmd

        rp = tmp_path / "result.json"
        cmd = build_fix_worker_cmd(tmp_path, rp, include_markdown_fix=False)
        assert "pre_commit_fix_worker" in " ".join(cmd)
        assert str(rp) in cmd
        assert str(tmp_path) in cmd

    def test_include_markdown_fix_flag_added(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_process import build_fix_worker_cmd

        rp = tmp_path / "result.json"
        cmd_with = build_fix_worker_cmd(tmp_path, rp, include_markdown_fix=True)
        cmd_without = build_fix_worker_cmd(tmp_path, rp, include_markdown_fix=False)
        assert "--include-markdown-fix" in cmd_with
        assert "--include-markdown-fix" not in cmd_without
