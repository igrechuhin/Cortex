"""The official Markdown route needs no tool manager and never retries lint failures."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools.execution import pre_commit_fix_worker as fixer
from cortex.tools.execution import pre_commit_worker as worker
from cortex.tools.execution.pre_commit_markdown_tool import (
    MarkdownToolError,
    resolve_approved_rumdl,
)
from cortex.tools.execution.pre_commit_rumdl_resolve import markdown_rumdl_argv
from tests.helpers.markdown_tool_fixtures import installed_markdown_tool


@pytest.mark.parametrize("with_fix", [False, True])
@pytest.mark.parametrize("with_config", [False, True])
def test_approved_argv_preserves_check_fix_and_config(
    tmp_path: Path, with_fix: bool, with_config: bool
) -> None:
    tool = installed_markdown_tool(tmp_path)
    config = tmp_path / ".rumdl.toml"
    if with_config:
        _ = config.write_text('[global]\ndisable = ["MD013"]\n')
    with patch(
        "cortex.tools.execution.pre_commit_markdown_tool.approved_environments",
        return_value=(tool.environment,),
    ):
        command = markdown_rumdl_argv(tmp_path, with_fix=with_fix)

    assert command == [
        str(tool.executable),
        "check",
        *(["--fix"] if with_fix else []),
        *(["--config", str(config)] if with_config else []),
    ]
    assert "uv" not in command and "run" not in command


def test_approved_installed_lint_reports_real_violation_without_uv_or_cache(
    tmp_path: Path,
) -> None:
    """Only this gate-run test executes the already approved installed native linter."""
    approved = resolve_approved_rumdl(tmp_path)
    source = tmp_path / "invalid.md"
    _ = source.write_text("# Heading\n\n### Skipped level\n")
    real_run = subprocess.run
    with (
        patch("shutil.which", side_effect=AssertionError("No global manager lookup")),
        patch("pathlib.Path.home", side_effect=AssertionError("No shared cache path")),
        patch(
            "cortex.tools.execution.pre_commit_worker.subprocess.run", wraps=real_run
        ) as launched,
    ):
        result = worker.run_markdown_lint(str(tmp_path))

    assert result["status"] == "error"
    assert result["files_with_errors"] == 1
    assert "MD001" in str(result["output"])
    launched.assert_called_once()
    assert launched.call_args.args[0][0] == str(approved)
    assert "uv" not in launched.call_args.args[0]


@pytest.mark.parametrize("returncode", [1, 2, 99])
def test_genuine_lint_failure_is_returned_without_alternate_launch(
    tmp_path: Path, returncode: int
) -> None:
    tool = installed_markdown_tool(tmp_path)
    completed = subprocess.CompletedProcess(
        [str(tool.executable)], returncode, "MD001 real finding", ""
    )
    with patch(
        "cortex.tools.execution.pre_commit_worker.subprocess.run",
        return_value=completed,
    ) as launched:
        result = worker.run_markdownlint_subprocess(
            tmp_path, [str(tool.executable), "check"], ["invalid.md"]
        )

    assert result["status"] == "error"
    assert "MD001" in str(result["output"])
    launched.assert_called_once()


@pytest.mark.parametrize(
    "failure", [FileNotFoundError("unavailable"), PermissionError("denied")]
)
def test_unusable_approved_executable_has_no_fallback(
    tmp_path: Path, failure: OSError
) -> None:
    with patch(
        "cortex.tools.execution.pre_commit_worker.subprocess.run", side_effect=failure
    ) as launched:
        result = worker.run_markdownlint_subprocess(
            tmp_path, [str(tmp_path / "approved-rumdl"), "check"], ["invalid.md"]
        )
    assert result["status"] == "error"
    launched.assert_called_once()


def test_no_approved_tool_blocks_check_and_fix_without_execution(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "document.md").write_text("# Document\n")
    with (
        patch(
            "cortex.tools.execution.pre_commit_markdown_tool.approved_environments",
            return_value=(),
        ),
        patch("cortex.tools.execution.pre_commit_worker.subprocess.run") as launched,
    ):
        checked = worker.run_markdown_lint(str(tmp_path))
        fixed = fixer.run_markdown_fix(str(tmp_path))

    assert checked["status"] == "error"
    assert fixed["success"] is False
    assert "No approved rumdl" in str(checked["error"])
    assert "No approved rumdl" in str(fixed["error"])
    launched.assert_not_called()


def test_fix_uses_same_approved_tool_and_does_not_retry_nonzero(tmp_path: Path) -> None:
    tool = installed_markdown_tool(tmp_path)
    source = tmp_path / "document.md"
    _ = source.write_text("# Document\n")
    completed = subprocess.CompletedProcess([], 1, "real fix failure", "")
    with (
        patch(
            "cortex.tools.execution.pre_commit_markdown_tool.approved_environments",
            return_value=(tool.environment,),
        ),
        patch(
            "cortex.tools.execution.pre_commit_fix_worker.subprocess.run",
            return_value=completed,
        ) as launched,
    ):
        result = fixer.run_markdown_fix(str(tmp_path))

    assert result["success"] is False
    launched.assert_called_once()
    assert launched.call_args.args[0] == [
        str(tool.executable),
        "check",
        "--fix",
        str(source),
    ]


def test_no_metadata_cannot_force_a_conventional_path(tmp_path: Path) -> None:
    with patch(
        "cortex.tools.execution.pre_commit_markdown_tool.approved_environments",
        return_value=(tmp_path,),
    ):
        with pytest.raises(MarkdownToolError, match="metadata_missing"):
            _ = markdown_rumdl_argv(tmp_path, with_fix=False)
