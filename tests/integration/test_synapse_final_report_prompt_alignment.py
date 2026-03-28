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


@pytest.mark.parametrize("filename", _PRIMARY_PROMPT_FILES)
def test_primary_prompt_has_final_report_section(filename: str) -> None:
    """Each primary prompt documents mandatory final-report format."""
    content = _read_prompt(filename)
    assert _FINAL_REPORT_HEADING in content
    assert _TEMPLATE_REF in content
    for marker in _REQUIRED_SECTION_MARKERS:
        assert marker in content, f"{filename} missing section marker {marker}"


def test_cursor_implement_code_agent_documents_final_report_handoff_split() -> None:
    """Cursor implement-code subagent defers user-facing final report to the orchestrator."""
    content = _read_cursor_implement_code_agent()
    assert _TEMPLATE_REF in content
    assert "orchestrator" in content
    assert "pipeline_handoff" in content
