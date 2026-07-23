"""Tests for the propose_framework_optimization MCP tool (thin handler)."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from cortex.tools.optimization.propose_framework_optimization import (
    propose_framework_optimization,
)

_VALID_MDC = "---\ndescription: Session-observed fix\n---\n\nBody.\n"


def _init_git_repo(root: Path) -> None:
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        _ = subprocess.run(args, cwd=root, check=True, capture_output=True)
    _ = (root / "README.md").write_text("seed\n", encoding="utf-8")
    _ = subprocess.run(
        ["git", "add", "README.md"], cwd=root, check=True, capture_output=True
    )
    _ = subprocess.run(
        ["git", "commit", "-q", "-m", "seed"], cwd=root, check=True, capture_output=True
    )


def _patch_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # AI: importlib.import_module (not `import ... as` / attribute access) is
    # required here: the optimization package's __init__.py rebinds the
    # attribute `propose_framework_optimization` on the package to the tool
    # *function* for re-export, so any dotted-attribute import resolves to the
    # function, not the submodule whose `get_or_resolve_project_root` needs
    # patching. importlib.import_module reads sys.modules directly instead.
    module = importlib.import_module(
        "cortex.tools.optimization.propose_framework_optimization"
    )

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_tool_success_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_git_repo(tmp_path)
    _patch_project_root(monkeypatch, tmp_path)
    changes_json = json.dumps(
        [{"relative_path": ".cortex/rules/general/fix.mdc", "new_content": _VALID_MDC}]
    )

    result = await propose_framework_optimization(
        changes_json=changes_json, rationale="Observed edge case"
    )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["result"]["self_test_passed"] is True
    assert data["result"]["changed_paths"] == [".cortex/rules/general/fix.mdc"]
    assert not (tmp_path / ".cortex" / "rules").exists()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_tool_self_test_failure_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_git_repo(tmp_path)
    _patch_project_root(monkeypatch, tmp_path)
    changes_json = json.dumps(
        [
            {
                "relative_path": ".cortex/rules/general/bad.mdc",
                "new_content": "no frontmatter",
            }
        ]
    )

    result = await propose_framework_optimization(
        changes_json=changes_json, rationale="Observed edge case"
    )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["result"]["self_test_passed"] is False
    assert data["result"]["failure_reason"] is not None


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_tool_rejects_malformed_changes_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_project_root(monkeypatch, tmp_path)

    result = await propose_framework_optimization(
        changes_json="{not-json}", rationale="Observed edge case"
    )

    data = json.loads(result)
    assert data["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_tool_rejects_empty_changes_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_project_root(monkeypatch, tmp_path)

    result = await propose_framework_optimization(changes_json="[]", rationale="x")

    data = json.loads(result)
    assert data["status"] == "error"
