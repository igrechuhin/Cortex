"""Ensure review/analyze prompts wire artifact filing into memory bank flow."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root


def _synapse_prompts_dir() -> Path:
    """Return path to Synapse prompt directory."""
    return get_cortex_path(get_project_root(), CortexResourceType.SYNAPSE) / "prompts"


def _read_prompt(name: str) -> str:
    """Read a prompt file by name from Synapse prompts."""
    return (_synapse_prompts_dir() / name).read_text(encoding="utf-8")


def test_review_prompt_has_threshold_gated_review_artifact_filing() -> None:
    """Review prompt files report artifacts when score meets configured threshold."""
    content = _read_prompt("review.md")
    assert "review_filing_threshold" in content
    assert ".cortex/config/lint-config.json" in content
    assert (
        'manage_file(operation="file_artifact", artifact_type="review_report"'
        in content
    )
    assert "overall_score >= threshold" in content


def test_analyze_prompt_always_files_session_analysis_artifact() -> None:
    """Analyze prompt always files session analysis artifacts."""
    content = _read_prompt("analyze.md")
    assert "File Session Analysis Artifact (Always)" in content
    assert (
        'manage_file(operation="file_artifact", artifact_type="session_analysis"'
        in content
    )
    assert "do not skip based on score" in content
