"""Ownership regression proof for installed skills, structural and Markdown gates."""

import json
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from cortex.core.constants import MAX_FUNCTION_LINES
from cortex.core.models import GitCommandResult
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.quality_scope import (
    SKILL_LOCK_NAME,
    filter_owned_files,
    installed_skill_roots,
)
from cortex.managers.initialization import get_project_root
from cortex.tools.execution.file_language_router import (
    collect_project_files,
    run_quality_checks_for_all_languages,
)
from cortex.tools.execution.pre_commit_pipeline_quality import (
    collect_git_delta_files,
    filter_preexisting_structural_violations,
)
from cortex.tools.execution.pre_commit_worker import collect_pre_commit_markdown_paths
from cortex.tools.files.markdown_link_validation import find_broken_links
from cortex.tools.files.markdown_lint_core import (
    get_all_markdown_files_for_lint,
    get_modified_markdown_files,
    run_markdown_lint_cli,
)


def _write_skill_lock(root: Path, name: str = "vendor", **changes: object) -> None:
    """Write synthetic external provenance, optionally malformed for negative cases."""
    entry: dict[str, object] = {
        "source": "publisher/package",
        "sourceType": "github",
        "skillPath": "skills/vendor/SKILL.md",
        "computedHash": "a" * 64,
    }
    entry.update(changes)
    _ = (root / SKILL_LOCK_NAME).write_text(
        json.dumps({"version": 1, "skills": {name: entry}}), encoding="utf-8"
    )


def _write_scope_file(root: Path, relative: str, content: str = "# Skill\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture()
def installed_vendor(tmp_path: Path) -> Path:
    _write_skill_lock(tmp_path)
    return _write_scope_file(tmp_path, ".agents/skills/vendor/SKILL.md").parent


def test_only_exact_locked_install_root_is_excluded(
    tmp_path: Path, installed_vendor: Path
) -> None:
    # Arrange
    vendor = installed_vendor / "SKILL.md"
    owned = [
        _write_scope_file(tmp_path, ".agents/skills/vendor-local/SKILL.md"),
        _write_scope_file(tmp_path, "src/vendor/SKILL.md"),
        _write_scope_file(tmp_path, "tests/vendor/SKILL.md"),
        _write_scope_file(tmp_path, ".codex/skills/vendor/SKILL.md"),
    ]
    # Act
    actual = filter_owned_files(tmp_path, [vendor, *owned])
    # Assert
    assert actual == owned
    assert filter_owned_files(tmp_path, [vendor.relative_to(tmp_path)]) == []


@pytest.mark.parametrize(
    "name", ["../src", "../../src", "/src", "a/b", "a\\b", "*", "."]
)
def test_forged_lock_name_cannot_exempt_owned_code(
    tmp_path: Path, installed_vendor: Path, name: str
) -> None:
    # Arrange
    _write_skill_lock(tmp_path, name)
    source = _write_scope_file(tmp_path, "src/invalid.py", "invalid source")
    # Act
    actual = filter_owned_files(tmp_path, [source, installed_vendor / "SKILL.md"])
    # Assert
    assert source in actual
    assert installed_skill_roots(tmp_path) == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", "../../src"),
        ("sourceType", "local"),
        ("computedHash", "invalid"),
        ("skillPath", "../src/SKILL.md"),
        ("skillPath", "/src/SKILL.md"),
        ("skillPath", "skills\\vendor\\SKILL.md"),
        ("skillPath", "src/invalid.py"),
    ],
)
def test_invalid_provenance_keeps_payload_checked(
    tmp_path: Path, installed_vendor: Path, field: str, value: str
) -> None:
    # Arrange
    _write_skill_lock(tmp_path, **{field: value})
    path = installed_vendor / "SKILL.md"
    # Act / Assert
    assert filter_owned_files(tmp_path, [path]) == [path]


@pytest.mark.parametrize("content", ["{", "{}", '{"version":2,"skills":{}}', "[]"])
def test_malformed_manifest_does_not_hide_files(tmp_path: Path, content: str) -> None:
    # Arrange
    _ = (tmp_path / SKILL_LOCK_NAME).write_text(content)
    # Act / Assert
    assert installed_skill_roots(tmp_path) == ()


def test_missing_manifest_or_skill_entry_remains_owned(tmp_path: Path) -> None:
    # Arrange / Act / Assert
    assert installed_skill_roots(tmp_path) == ()
    _write_skill_lock(tmp_path)
    assert installed_skill_roots(tmp_path) == ()


@pytest.mark.parametrize(
    "ancestor", [".agents", ".agents/skills", ".agents/skills/vendor"]
)
def test_symlinked_install_ancestor_cannot_exempt_source(
    tmp_path: Path, ancestor: str
) -> None:
    # Arrange
    source = _write_scope_file(tmp_path, "src/SKILL.md")
    _write_skill_lock(tmp_path)
    link = tmp_path / ancestor
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(source.parent, target_is_directory=True)
    # Act / Assert
    assert installed_skill_roots(tmp_path) == ()
    assert filter_owned_files(tmp_path, [source]) == [source]


def test_vendor_file_symlink_into_source_is_checked(
    tmp_path: Path, installed_vendor: Path
) -> None:
    # Arrange
    source = _write_scope_file(tmp_path, "src/invalid.py", "invalid source")
    alias = installed_vendor / "alias.py"
    alias.symlink_to(source)
    # Act / Assert
    assert filter_owned_files(tmp_path, [source, alias]) == [source, alias]


def _write_oversized_scope_source(root: Path, relative: str) -> Path:
    body = "\n".join(f"    value_{i} = {i}" for i in range(MAX_FUNCTION_LINES + 5))
    return _write_scope_file(root, relative, f"def oversized():\n{body}\n")


@pytest.mark.parametrize("explicit", [False, True])
def test_structural_gate_rejects_owned_source_and_local_skill(
    tmp_path: Path, installed_vendor: Path, explicit: bool
) -> None:
    # Arrange
    _ = installed_vendor
    vendor = _write_oversized_scope_source(tmp_path, ".agents/skills/vendor/code.py")
    local = _write_oversized_scope_source(tmp_path, ".agents/skills/local/code.py")
    source = _write_oversized_scope_source(tmp_path, "src/invalid.py")
    test_file = _write_oversized_scope_source(tmp_path, "tests/test_invalid.py")
    synapse = get_cortex_path(get_project_root(None), CortexResourceType.SYNAPSE)
    link = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(synapse, target_is_directory=True)
    # Act
    _, violations = run_quality_checks_for_all_languages(
        tmp_path, files=[vendor, local, source, test_file] if explicit else None
    )
    # Assert
    paths = {violation.file for violation in violations}
    assert paths == {".agents/skills/local/code.py", "src/invalid.py"} | (
        {"tests/test_invalid.py"} if explicit else set()
    )
    assert vendor not in collect_project_files(tmp_path)


def test_markdown_worker_and_full_collection_share_scope(
    tmp_path: Path, installed_vendor: Path
) -> None:
    # Arrange
    _ = _write_scope_file(
        tmp_path, ".agents/skills/vendor/README.md", "[x](upstream.md)"
    )
    local = _write_scope_file(tmp_path, ".agents/skills/local/SKILL.md")
    # Act
    expected = get_all_markdown_files_for_lint(tmp_path, max_files=None)
    actual = collect_pre_commit_markdown_paths(tmp_path)
    # Assert
    assert [str(path) for path in expected] == actual
    assert local in expected
    assert not any(path.is_relative_to(installed_vendor) for path in expected)


def test_full_markdown_scope_does_not_truncate_after_500(tmp_path: Path) -> None:
    # Arrange
    for index in range(501):
        _ = _write_scope_file(tmp_path, f"docs/{index:03}.md")
    # Act / Assert
    assert len(get_all_markdown_files_for_lint(tmp_path)) == 500
    assert len(collect_pre_commit_markdown_paths(tmp_path)) == 501


def test_markdown_cli_rejects_local_doc_but_preserves_vendor(
    tmp_path: Path, installed_vendor: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    vendor = _write_scope_file(tmp_path, ".agents/skills/vendor/README.md", "#Bad\n")
    local = _write_scope_file(tmp_path, ".agents/skills/local/SKILL.md", "#Bad\n")
    _ = installed_vendor
    monkeypatch.chdir(tmp_path)
    # Act / Assert
    assert run_markdown_lint_cli() != 0
    _ = local.write_text("# Good\n")
    assert run_markdown_lint_cli() == 0
    assert vendor.read_text() == "#Bad\n"


def test_links_validate_owned_skills_and_integration_references(
    tmp_path: Path, installed_vendor: Path
) -> None:
    # Arrange
    _ = (installed_vendor / "SKILL.md").write_text("[upstream](missing.md)\n")
    _ = _write_scope_file(
        tmp_path, ".agents/skills/local/SKILL.md", "[local](missing.md)\n"
    )
    _ = _write_scope_file(
        tmp_path,
        "docs/integration.md",
        "[installed](../.agents/skills/vendor/SKILL.md)\n"
        + "[missing](../.agents/skills/vendor/missing.md)\n",
    )
    # Act
    violations = find_broken_links(tmp_path)
    # Assert
    assert {violation.source_file for violation in violations} == {
        ".agents/skills/local/SKILL.md",
        "docs/integration.md",
    }
    assert len(violations) == 2


@pytest.mark.parametrize("explicit", [False, True])
def test_source_symlink_to_vendor_retains_owned_violation(
    tmp_path: Path, installed_vendor: Path, explicit: bool
) -> None:
    # Arrange
    _ = installed_vendor
    vendor = _write_oversized_scope_source(tmp_path, ".agents/skills/vendor/code.py")
    source = tmp_path / "src" / "alias.py"
    source.parent.mkdir()
    source.symlink_to(vendor)
    synapse = get_cortex_path(get_project_root(None), CortexResourceType.SYNAPSE)
    link = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE)
    link.parent.mkdir(parents=True)
    link.symlink_to(synapse, target_is_directory=True)
    # Act
    files, functions = run_quality_checks_for_all_languages(
        tmp_path, files=[source] if explicit else None
    )
    _, incremental = filter_preexisting_structural_violations(
        tmp_path, [source], files, functions
    )
    # Assert
    assert source in collect_project_files(tmp_path)
    assert {item.file for item in functions} == {"src/alias.py"}
    assert incremental == functions


def test_git_candidates_keep_source_symlink_identity(
    tmp_path: Path, installed_vendor: Path
) -> None:
    # Arrange
    source = tmp_path / "src" / "alias.py"
    source.parent.mkdir()
    source.symlink_to(installed_vendor / "SKILL.md")
    result = CompletedProcess(args=["git"], returncode=0, stdout="src/alias.py\n")
    # Act
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.subprocess.run",
        return_value=result,
    ):
        candidates = collect_git_delta_files(tmp_path)
    # Assert
    assert candidates == [source]


@pytest.mark.asyncio
async def test_modified_markdown_keeps_only_owned_files(
    tmp_path: Path, installed_vendor: Path
) -> None:
    # Arrange
    local = _write_scope_file(tmp_path, ".agents/skills/local/SKILL.md")
    vendor = installed_vendor / "SKILL.md"
    result = GitCommandResult(
        success=True,
        stdout="\n".join(str(path.relative_to(tmp_path)) for path in (local, vendor)),
        stderr="",
        returncode=0,
    )
    # Act
    with patch(
        "cortex.tools.files.markdown_lint_core.run_command", return_value=result
    ):
        actual = await get_modified_markdown_files(tmp_path, include_untracked=True)
    # Assert
    assert actual == [local]
