"""Tests for the detached fix-quality pipeline.

Covers:
- fix_quality_issues_impl: success/error/timeout envelopes → correct JSON
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

from cortex.core.models import ModelDict
from cortex.tools.execution.pre_commit_fix_quality import (
    FixQualityResult,
    parse_fix_envelope,
)

# ---------------------------------------------------------------------------
# _parse_fix_envelope
# ---------------------------------------------------------------------------


class TestParseFixEnvelope:
    """Unit tests for the envelope parser (no I/O)."""

    def test_success_envelope_returns_valid_json(self) -> None:
        # Arrange
        envelope = cast(
            ModelDict,
            {
                "version": 1,
                "status": "completed",
                "result": {
                    "results": {
                        "fix_errors": {
                            "errors": ["E1"],
                            "warnings": ["W1"],
                            "files_modified": ["a.py"],
                        },
                        "format": {"files_formatted": 2},
                        "type_check": {"errors": [], "warnings": []},
                    },
                    "files_modified": ["a.py"],
                },
                "markdown_result": {
                    "success": True,
                    "files_fixed": 1,
                    "results": [{"file": "README.md", "fixed": True}],
                },
            },
        )
        # Act
        out = parse_fix_envelope(envelope)
        data = json.loads(out)
        result = FixQualityResult(**data)
        # Assert
        assert result.status.value == "success"
        assert result.errors_fixed == 1
        assert result.warnings_fixed == 1
        assert result.formatting_issues_fixed == 2
        assert result.markdown_issues_fixed == 1
        assert "a.py" in result.files_modified
        assert "README.md" in result.files_modified

    def test_error_envelope_returns_error_json(self) -> None:
        # Arrange
        envelope = cast(
            ModelDict, {"version": 1, "status": "error", "error": "worker crashed"}
        )
        # Act
        out = parse_fix_envelope(envelope)
        data = json.loads(out)
        # Assert
        assert data["status"] == "error"
        assert "error_type" in data

    def test_timeout_envelope_returns_error_json(self) -> None:
        # Arrange
        envelope = cast(
            ModelDict,
            {"version": 1, "status": "timeout", "error": "Timeout after 960s"},
        )
        # Act
        out = parse_fix_envelope(envelope)
        data = json.loads(out)
        # Assert
        assert data["status"] == "error"

    def test_empty_result_returns_zero_counts(self) -> None:
        # Arrange
        envelope = cast(ModelDict, {"version": 1, "status": "completed", "result": {}})
        # Act
        out = parse_fix_envelope(envelope)
        data = json.loads(out)
        result = FixQualityResult(**data)
        # Assert
        assert result.status.value == "success"
        assert result.errors_fixed == 0
        assert result.markdown_issues_fixed == 0

    def test_no_markdown_result_is_handled(self) -> None:
        # Arrange
        envelope = cast(
            ModelDict,
            {
                "version": 1,
                "status": "completed",
                "result": {"results": {}, "files_modified": []},
            },
        )
        # Act
        out = parse_fix_envelope(envelope)
        data = json.loads(out)
        # Assert — no KeyError
        assert data["status"] == "success"
        assert data["markdown_issues_fixed"] == 0

    def test_parse_fix_envelope_override_files_modified(self) -> None:
        # Arrange
        envelope = cast(
            ModelDict,
            {
                "version": 1,
                "status": "completed",
                "result": {
                    "results": {
                        "fix_errors": {"errors": [], "warnings": []},
                        "format": {"files_formatted": 0},
                        "type_check": {"errors": [], "warnings": []},
                    },
                    "files_modified": ["noise.md"],
                },
            },
        )
        # Act
        out = parse_fix_envelope(
            envelope, files_modified_override=["actual.py", "actual_test.py"]
        )
        data = json.loads(out)

        # Assert
        assert data["status"] == "success"
        assert data["files_modified"] == ["actual.py", "actual_test.py"]


# ---------------------------------------------------------------------------
# fix_quality_issues_impl — detached spawn + poll
# ---------------------------------------------------------------------------


class TestFixQualityIssuesImpl:
    """Tests for fix_quality_issues_impl using mocked detached worker."""

    @pytest.mark.asyncio
    async def test_success_envelope_returned_from_poll(self, tmp_path: Path) -> None:
        # Arrange
        envelope = cast(
            ModelDict,
            {
                "version": 1,
                "status": "completed",
                "result": {
                    "results": {
                        "fix_errors": {
                            "errors": [],
                            "warnings": [],
                            "files_modified": [],
                        },
                        "format": {"files_formatted": 0},
                        "type_check": {"errors": [], "warnings": []},
                    },
                    "files_modified": [],
                },
            },
        )
        with (
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.start_fix_job_impl",
                return_value={"job_id": "abc123", "status": "started"},
            ),
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import (
                fix_quality_issues_impl,
            )

            # Act
            out = await fix_quality_issues_impl(
                tmp_path, include_untracked_markdown=True, ctx=None
            )

        # Assert
        data = json.loads(out)
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_error_envelope_surfaced_as_error_json(self, tmp_path: Path) -> None:
        # Arrange
        envelope = cast(
            ModelDict, {"version": 1, "status": "error", "error": "ruff not found"}
        )
        with (
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.start_fix_job_impl",
                return_value={"job_id": "abc123", "status": "started"},
            ),
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import (
                fix_quality_issues_impl,
            )

            # Act
            out = await fix_quality_issues_impl(
                tmp_path, include_untracked_markdown=False, ctx=None
            )

        # Assert
        data = json.loads(out)
        assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_timeout_envelope_surfaced_as_error_json(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        envelope = cast(
            ModelDict,
            {"version": 1, "status": "timeout", "error": "Timeout after 960s"},
        )
        with (
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.start_fix_job_impl",
                return_value={"job_id": "xyz", "status": "started"},
            ),
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import (
                fix_quality_issues_impl,
            )

            # Act
            out = await fix_quality_issues_impl(
                tmp_path, include_untracked_markdown=False, ctx=None
            )

        # Assert
        data = json.loads(out)
        assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_poll_called_with_ctx_for_heartbeats(self, tmp_path: Path) -> None:
        # Arrange — ctx must be forwarded so poll_for_result sends progress
        mock_ctx = AsyncMock()
        envelope = cast(
            ModelDict,
            {
                "version": 1,
                "status": "completed",
                "result": {"results": {}, "files_modified": []},
            },
        )
        poll_mock = AsyncMock(return_value=envelope)
        with (
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.start_fix_job_impl",
                return_value={"job_id": "abc", "status": "started"},
            ),
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.poll_for_result",
                poll_mock,
            ),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import (
                fix_quality_issues_impl,
            )

            # Act
            _ = await fix_quality_issues_impl(
                tmp_path, include_untracked_markdown=True, ctx=mock_ctx
            )

        # Assert — poll_for_result received the ctx
        _, kwargs = poll_mock.call_args
        assert kwargs.get("ctx") is mock_ctx or poll_mock.call_args[0][1] is mock_ctx

    @pytest.mark.asyncio
    async def test_uses_git_delta_for_files_modified(self, tmp_path: Path) -> None:
        # Arrange
        envelope = cast(
            ModelDict,
            {
                "version": 1,
                "status": "completed",
                "result": {
                    "results": {
                        "fix_errors": {"errors": [], "warnings": []},
                        "format": {"files_formatted": 0},
                        "type_check": {"errors": [], "warnings": []},
                    },
                    "files_modified": ["noise.md"],
                },
            },
        )
        with (
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.start_fix_job_impl",
                return_value={"job_id": "abc123", "status": "started"},
            ),
            patch(
                "cortex.tools.execution.pre_commit_fix_quality.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
            patch(
                "cortex.tools.execution.pre_commit_fix_quality._get_tracked_git_changes",
                side_effect=[{"already_dirty.py"}, {"already_dirty.py", "new_fix.py"}],
            ),
        ):
            from cortex.tools.execution.pre_commit_fix_quality import (
                fix_quality_issues_impl,
            )

            # Act
            out = await fix_quality_issues_impl(
                tmp_path, include_untracked_markdown=True, ctx=None
            )

        # Assert
        data = json.loads(out)
        assert data["status"] == "success"
        assert data["files_modified"] == ["new_fix.py"]


# ---------------------------------------------------------------------------
# spawn_detached_fix_worker — result path uses fix prefix
# ---------------------------------------------------------------------------


class TestSpawnDetachedFixWorker:
    """Tests for spawn_detached_fix_worker."""

    def test_result_path_uses_fix_prefix(self, tmp_path: Path) -> None:
        # Arrange
        from cortex.tools.execution.pre_commit_detached import spawn_detached_fix_worker

        with patch(
            "cortex.tools.execution.pre_commit_detached.spawn_detached_process"
        ) as mock_spawn:
            mock_spawn.return_value = None
            # Act
            rp = spawn_detached_fix_worker(
                tmp_path, include_markdown_fix=False, args_hash="abc123"
            )

        # Assert
        assert "pre_commit_fix_result_" in rp.name
        assert "abc123" in rp.name

    def test_no_fix_prefix_in_read_only_results(self, tmp_path: Path) -> None:
        # Arrange — read-only worker uses different prefix
        from cortex.tools.execution.pre_commit_process import pre_commit_result_path
        from cortex.tools.execution.session_paths import session_dir

        rp = pre_commit_result_path(session_dir(tmp_path), "abc123")
        # Assert — different prefix from fix worker
        assert "pre_commit_fix_result_" not in rp.name


# ---------------------------------------------------------------------------
# start_fix_job_impl — always clears and spawns fresh
# ---------------------------------------------------------------------------


class TestStartFixJobImpl:
    """Tests for start_fix_job_impl."""

    def test_clears_prior_result_before_spawning(self, tmp_path: Path) -> None:
        # Arrange
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
            # Act
            result = start_fix_job_impl(tmp_path, include_markdown_fix=False)

        # Assert — old file cleared, new job started
        assert not rp.exists()
        assert result["status"] == "started"

    def test_returns_started_status(self, tmp_path: Path) -> None:
        # Arrange
        from cortex.tools.execution.pre_commit_detached import start_fix_job_impl

        with patch(
            "cortex.tools.execution.pre_commit_detached.spawn_detached_fix_worker"
        ) as mock_spawn:
            mock_spawn.return_value = tmp_path / "result.json"
            # Act
            result = start_fix_job_impl(tmp_path, include_markdown_fix=True)

        # Assert
        assert result["status"] == "started"
        assert "job_id" in result


# ---------------------------------------------------------------------------
# build_fix_worker_cmd
# ---------------------------------------------------------------------------


class TestBuildFixWorkerCmd:
    """Tests for build_fix_worker_cmd."""

    def test_includes_fix_worker_module(self, tmp_path: Path) -> None:
        # Arrange
        from cortex.tools.execution.pre_commit_process import build_fix_worker_cmd

        rp = tmp_path / "result.json"
        # Act
        cmd = build_fix_worker_cmd(tmp_path, rp, include_markdown_fix=False)
        # Assert
        assert "pre_commit_fix_worker" in " ".join(cmd)
        assert str(rp) in cmd
        assert str(tmp_path) in cmd

    def test_include_markdown_fix_flag_added(self, tmp_path: Path) -> None:
        # Arrange
        from cortex.tools.execution.pre_commit_process import build_fix_worker_cmd

        rp = tmp_path / "result.json"
        # Act
        cmd_with = build_fix_worker_cmd(tmp_path, rp, include_markdown_fix=True)
        cmd_without = build_fix_worker_cmd(tmp_path, rp, include_markdown_fix=False)
        # Assert
        assert "--include-markdown-fix" in cmd_with
        assert "--include-markdown-fix" not in cmd_without
