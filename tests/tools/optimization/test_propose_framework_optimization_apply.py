"""Tests for propose_framework_optimization change application inside a worktree."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.tools.optimization.propose_framework_optimization_allowlist import (
    PathAllowlistError,
)
from cortex.tools.optimization.propose_framework_optimization_apply import (
    apply_changes_to_worktree,
)
from cortex.tools.optimization.propose_framework_optimization_models import (
    ProposedFileChange,
)


def test_applies_valid_changes_and_creates_parent_dirs(tmp_path: Path) -> None:
    changes = [
        ProposedFileChange(
            relative_path=".cortex/rules/general/new-rule.mdc",
            new_content="---\ndescription: x\n---\nBody",
        ),
        ProposedFileChange(
            relative_path=".cortex/synapse/rules/manifest.json",
            new_content='{"version": "1.0"}',
        ),
    ]

    targets = apply_changes_to_worktree(tmp_path, changes)

    assert len(targets) == 2
    assert targets[0].read_text(encoding="utf-8") == "---\ndescription: x\n---\nBody"
    assert targets[1].read_text(encoding="utf-8") == '{"version": "1.0"}'


def test_rejects_traversal_before_writing_any_file(tmp_path: Path) -> None:
    changes = [
        ProposedFileChange(
            relative_path=".cortex/rules/ok.mdc",
            new_content="---\ndescription: x\n---\n",
        ),
        ProposedFileChange(
            relative_path="../../src/cortex/main.py", new_content="malicious"
        ),
    ]

    with pytest.raises(PathAllowlistError):
        _ = apply_changes_to_worktree(tmp_path, changes)

    assert not (tmp_path / ".cortex" / "rules" / "ok.mdc").exists()
    assert not (tmp_path.parent.parent / "src" / "cortex" / "main.py").exists()
