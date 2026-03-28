"""
Structural checks for mandatory final-report guidance in primary Synapse prompts.

Ensures each primary workflow prompt references the canonical template doc and
lists the required closing `##` section titles (user-facing markdown narrative).
"""

from pathlib import Path

import pytest

from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
)
from cortex.managers.initialization import get_project_root

_PRIMARY_PROMPT_FILES: tuple[str, ...] = (
    "commit.md",
    "implement-next-roadmap-step.md",
    "fix.md",
    "analyze.md",
    "create-plan.md",
    "review.md",
)

_FINAL_REPORT_HEADING = "## Final report (required format)"
_TEMPLATE_REF = "docs/guides/synapse-final-report-templates.md"

_REQUIRED_SECTION_MARKERS: tuple[str, ...] = (
    "`## Status`",
    "`## Scope`",
    "`## What ran`",
    "`## Key results`",
    "`## Memory bank and roadmap`",
    "`## Blockers and follow-ups`",
)


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return get_project_root()


def _synapse_prompts_dir() -> Path:
    """Return path to Synapse prompts directory."""
    return get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE) / "prompts"


def _cursor_implement_code_agent_path() -> Path:
    """Return Synapse source path for the Cursor implement-code subagent."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "cursor-agents"
        / "implement-code.md"
    )


def _read_cursor_implement_code_agent() -> str:
    """Read Synapse source for the Cursor implement-code subagent."""
    path = _cursor_implement_code_agent_path()
    if not path.exists():
        pytest.skip(
            f"(ref: cleanup-skipped-legacy-tests) cursor agent source not found at {path}"
        )
    return path.read_text()


def _read_prompt(name: str) -> str:
    """Read a primary Synapse prompt by filename."""
    path = _synapse_prompts_dir() / name
    if not path.exists():
        pytest.skip(f"(ref: cleanup-skipped-legacy-tests) prompt not found at {path}")
    return path.read_text()


def _cursor_commands_md_paths() -> list[Path]:
    """Return sorted paths to `.cursor/commands/*.md` (non-empty)."""
    root = _repo_root() / ".cursor" / "commands"
    if not root.is_dir():
        pytest.skip(
            "(ref: cleanup-skipped-legacy-tests) .cursor/commands directory not found"
        )
    paths = sorted(p for p in root.glob("*.md") if p.is_file())
    assert paths, f"expected at least one *.md under {root}"
    return paths


def _assert_final_report_markers(path: Path, content: str) -> None:
    """Shared structural checks for template ref, heading, and section markers."""
    assert _FINAL_REPORT_HEADING in content, f"{path} missing final report heading"
    assert _TEMPLATE_REF in content, f"{path} missing template reference"
    for marker in _REQUIRED_SECTION_MARKERS:
        assert marker in content, f"{path} missing section marker {marker}"


@pytest.mark.parametrize("filename", _PRIMARY_PROMPT_FILES)
def test_primary_prompt_has_final_report_section(filename: str) -> None:
    """Each primary prompt documents mandatory final-report format."""
    path = _synapse_prompts_dir() / filename
    content = _read_prompt(filename)
    _assert_final_report_markers(path, content)


def test_cursor_commands_align_with_final_report_template() -> None:
    """Cursor workflow commands mirror Synapse final-report expectations."""
    for path in _cursor_commands_md_paths():
        _assert_final_report_markers(path, path.read_text())


def test_cursor_implement_code_agent_documents_final_report_handoff_split() -> None:
    """Cursor implement-code subagent defers user-facing final report to the orchestrator."""
    content = _read_cursor_implement_code_agent()
    assert _TEMPLATE_REF in content
    assert "orchestrator" in content
    assert "pipeline_handoff" in content
