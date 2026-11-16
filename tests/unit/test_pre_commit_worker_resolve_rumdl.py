"""Installed Markdown tool approval is pinned, bounded and package-compatible."""

import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools.execution.pre_commit_markdown_tool import (
    APPROVED_RUMDL_VERSION,
    MarkdownToolError,
    resolve_approved_rumdl,
)
from cortex.tools.execution.pre_commit_rumdl_resolve import resolve_rumdl_path
from tests.helpers.markdown_tool_fixtures import (
    MarkdownToolFixture,
    installed_markdown_tool,
)


def test_recorded_project_tool_is_selected_without_an_interpreter_probe(
    tmp_path: Path,
) -> None:
    tool = installed_markdown_tool(tmp_path)
    with (
        patch(
            "cortex.tools.execution.pre_commit_markdown_tool.approved_environments",
            return_value=(tool.environment,),
        ),
        patch(
            "subprocess.run", side_effect=AssertionError("No interpreter or tool probe")
        ),
    ):
        assert resolve_rumdl_path(tmp_path) == str(tool.executable)


def test_running_package_environment_works_without_a_source_lockfile(
    tmp_path: Path,
) -> None:
    tool = installed_markdown_tool(tmp_path)
    with patch.object(sys, "prefix", str(tool.environment)):
        assert resolve_approved_rumdl() == tool.executable
    assert not (tmp_path / "uv.lock").exists()


def test_unattached_virtual_env_and_global_path_do_not_grant_tool_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    external = tmp_path / "external"
    tool = installed_markdown_tool(external)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("VIRTUAL_ENV", str(tool.environment))
    monkeypatch.setenv("PATH", str(tool.executable.parent))
    with patch.object(sys, "prefix", str(tmp_path / "empty-package-env")):
        with pytest.raises(MarkdownToolError, match="metadata_missing"):
            _ = resolve_approved_rumdl(project)


@pytest.mark.parametrize(
    "defect",
    [
        "version",
        "name",
        "metadata_missing",
        "record_missing",
        "digest",
        "size",
        "record_path",
        "duplicate_record",
        "executable_missing",
        "not_executable",
        "executable_escape",
        "metadata_oversized",
    ],
)
def test_unapproved_or_corrupt_installed_tool_fails_closed(
    tmp_path: Path, defect: str
) -> None:
    tool = installed_markdown_tool(tmp_path)
    _corrupt_tool(tool, defect)
    with patch(
        "cortex.tools.execution.pre_commit_markdown_tool.approved_environments",
        return_value=(tool.environment,),
    ):
        with pytest.raises(MarkdownToolError, match="No approved rumdl"):
            _ = resolve_approved_rumdl(tmp_path)


def _corrupt_metadata(tool: MarkdownToolFixture, defect: str) -> bool:
    metadata = tool.metadata / "METADATA"
    texts = {
        "version": "Name: rumdl\nVersion: 99.0.0\n",
        "name": f"Name: foreign-tool\nVersion: {APPROVED_RUMDL_VERSION}\n",
        "metadata_oversized": "x" * 131073,
    }
    if defect in texts:
        _ = metadata.write_text(texts[defect])
    elif defect == "metadata_missing":
        metadata.unlink()
    else:
        return False
    return True


def _corrupt_tool(tool: MarkdownToolFixture, defect: str) -> None:
    if _corrupt_metadata(tool, defect):
        return
    if defect == "record_missing":
        tool.record.unlink()
    elif defect == "digest":
        _ = tool.executable.write_bytes(b"Tampered after installation")
    elif defect == "size":
        text = tool.record.read_text().rstrip().rsplit(",", 1)[0] + ",1\n"
        _ = tool.record.write_text(text)
    elif defect == "record_path":
        _ = tool.record.write_text("unrelated,sha256=unrelated,1\n")
    elif defect == "duplicate_record":
        _ = tool.record.write_text(tool.record.read_text() * 2)
    elif defect == "executable_missing":
        tool.executable.unlink()
    elif defect == "not_executable":
        tool.executable.chmod(0o644)
    elif defect == "executable_escape":
        outside = tool.environment.parent / "outside-tool"
        _ = tool.executable.rename(outside)
        tool.executable.symlink_to(outside)


def test_packaged_pin_matches_declared_dependencies_and_lock() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    locked = tomllib.loads((root / "uv.lock").read_text())
    expected = f"rumdl=={APPROVED_RUMDL_VERSION}"
    # BELIEF: These checked-in TOML tables are the package's declared dependency contract.
    assert expected in project["project"]["dependencies"]
    assert expected in project["dependency-groups"]["dev"]
    versions = [
        package["version"]
        for package in locked["package"]
        if package["name"] == "rumdl"
    ]
    assert versions == [APPROVED_RUMDL_VERSION]
    cortex = next(
        package for package in locked["package"] if package["name"] == "cortex"
    )
    assert {
        entry["specifier"]
        for entry in cortex["metadata"]["requires-dist"]
        if entry["name"] == "rumdl"
    } == {f"=={APPROVED_RUMDL_VERSION}"}
