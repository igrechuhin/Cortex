"""
Structural checks for mandatory final-report guidance in primary Synapse prompts.

Ensures each primary workflow prompt references the canonical template doc and
uses the correct report structure (Pipeline, Diagnostic, or Artifact).

Canonical workflows live under `.cortex/synapse/prompts/`.
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
    "do.md",
    "fix.md",
    "analyze.md",
    "plan.md",
    "review.md",
)

_FINAL_REPORT_HEADING = "## Final report (required format)"
_TEMPLATE_REF = "docs/guides/synapse-final-report-templates.md"

# Report type classification
_PIPELINE_PROMPTS = ("commit.md", "do.md")
_DIAGNOSTIC_PROMPTS = ("fix.md",)
_ARTIFACT_PROMPTS = ("analyze.md", "plan.md", "review.md")

# Required section markers by report type (backtick-wrapped in prompt examples)
_PIPELINE_MARKERS: tuple[str, ...] = (
    "## Result",
    "## Phases",
    "## Artifacts",
    "## Next",
)

_DIAGNOSTIC_MARKERS: tuple[str, ...] = (
    "## Result",
    "## Diagnosis",
    "## Iterations",
    "## Changes",
    "## Next",
)

_ARTIFACT_MARKERS: tuple[str, ...] = (
    "## Result",
    "## Output",
    "## Next",
)

_REVIEW_MARKERS: tuple[str, ...] = (
    "## Result",
    "## Scores",
    "## Issues",
    "## Next",
)


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return get_project_root()


def _synapse_prompts_dir() -> Path:
    """Return path to Synapse prompts directory."""
    return get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE) / "prompts"


def _claude_implement_code_agent_path() -> Path:
    """Return Synapse source path for the implement-code Claude Code subagent."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "claude-agents"
        / "implement-code.md"
    )


def _read_claude_implement_code_agent() -> str:
    """Read Synapse source for the implement-code Claude Code subagent."""
    path = _claude_implement_code_agent_path()
    if not path.exists():
        pytest.skip(
            f"(ref: cleanup-skipped-legacy-tests) claude agent source not found at {path}"
        )
    return path.read_text()


def _read_prompt(name: str) -> str:
    """Read a primary Synapse prompt by filename."""
    path = _synapse_prompts_dir() / name
    if not path.exists():
        pytest.skip(f"(ref: cleanup-skipped-legacy-tests) prompt not found at {path}")
    return path.read_text()


def _get_required_markers(filename: str) -> tuple[str, ...]:
    """Return the required section markers based on prompt type."""
    if filename in _PIPELINE_PROMPTS:
        return _PIPELINE_MARKERS
    if filename in _DIAGNOSTIC_PROMPTS:
        return _DIAGNOSTIC_MARKERS
    if filename == "review.md":
        return _REVIEW_MARKERS
    if filename in _ARTIFACT_PROMPTS:
        return _ARTIFACT_MARKERS
    # Default fallback
    return _ARTIFACT_MARKERS


def _assert_final_report_markers(path: Path, content: str, filename: str = "") -> None:
    """Shared structural checks for template ref, heading, and section markers."""
    assert _FINAL_REPORT_HEADING in content, f"{path} missing final report heading"
    assert _TEMPLATE_REF in content, f"{path} missing template reference"

    # Get appropriate markers based on filename or path
    effective_filename = filename or path.name
    markers = _get_required_markers(effective_filename)

    for marker in markers:
        assert marker in content, f"{path} missing section marker {marker}"


@pytest.mark.parametrize("filename", _PRIMARY_PROMPT_FILES)
def test_primary_prompt_has_final_report_section(filename: str) -> None:
    """Each primary prompt documents mandatory final-report format."""
    path = _synapse_prompts_dir() / filename
    content = _read_prompt(filename)
    _assert_final_report_markers(path, content, filename)


def test_claude_implement_code_agent_documents_final_report_handoff_split() -> None:
    """implement-code Claude Code subagent defers user-facing final report to orchestrator."""
    content = _read_claude_implement_code_agent()
    assert _TEMPLATE_REF in content
    assert "orchestrator" in content
    assert "pipeline_handoff" in content
