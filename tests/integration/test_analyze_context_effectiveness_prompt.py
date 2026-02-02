"""
Integration tests for Phase 48: Analyze context effectiveness prompt.

Verifies that analyze-context-effectiveness.md is in the prompts manifest
and contains required sections (Pre-Analysis Checklist, Usage Analysis,
Scoring Metrics, Feedback Categories, Feedback Schema).
"""

from pathlib import Path
from typing import cast

import pytest


def _get_prompts_from_manifest(
    manifest_data: dict[str, object],
) -> list[dict[str, object]]:
    """Extract general.prompts list from manifest; return empty list if missing."""
    categories = manifest_data.get("categories")
    if not isinstance(categories, dict):
        return []
    categories = cast(dict[str, object], categories)
    general = categories.get("general")
    if not isinstance(general, dict):
        return []
    general = cast(dict[str, object], general)
    prompts_val = general.get("prompts")
    if not isinstance(prompts_val, list):
        return []
    prompts_val = cast(list[object], prompts_val)
    return [cast(dict[str, object], p) for p in prompts_val if isinstance(p, dict)]


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return Path(__file__).resolve().parents[2]


def _prompts_dir() -> Path:
    """Return path to Synapse prompts directory."""
    return _repo_root() / ".cortex" / "synapse" / "prompts"


def _analyze_context_effectiveness_prompt_path() -> Path:
    """Return path to analyze-context-effectiveness prompt."""
    return _prompts_dir() / "analyze-context-effectiveness.md"


def _manifest_path() -> Path:
    """Return path to prompts-manifest.json."""
    return _prompts_dir() / "prompts-manifest.json"


class TestAnalyzeContextEffectivenessInManifest:
    """Assert Phase 48 analyze-context-effectiveness is in prompts manifest."""

    @pytest.fixture
    def manifest_data(self) -> dict[str, object] | None:
        """Load manifest; skip if missing."""
        path = _manifest_path()
        if not path.exists():
            pytest.skip(
                f"Manifest not found at {path} (e.g. synapse submodule not present)"
            )
        import json

        data: object = json.loads(path.read_text())
        return cast(dict[str, object], data) if isinstance(data, dict) else None

    def test_analyze_context_effectiveness_listed_in_manifest(
        self, manifest_data: dict[str, object] | None
    ) -> None:
        """Manifest general category includes analyze-context-effectiveness prompt."""
        assert manifest_data is not None
        prompts = _get_prompts_from_manifest(manifest_data)
        files = [str(p.get("file", "")) for p in prompts]
        assert "analyze-context-effectiveness.md" in files

    def test_analyze_context_effectiveness_has_name_and_description(
        self, manifest_data: dict[str, object] | None
    ) -> None:
        """Analyze context effectiveness entry has name and description."""
        assert manifest_data is not None
        prompts = _get_prompts_from_manifest(manifest_data)
        entry = next(
            (p for p in prompts if p.get("file") == "analyze-context-effectiveness.md"),
            None,
        )
        assert entry is not None
        assert "name" in entry and "description" in entry
        desc = entry.get("description")
        desc_str = desc if isinstance(desc, str) else ""
        assert "context" in desc_str.lower() or "effectiveness" in desc_str.lower()


class TestAnalyzeContextEffectivenessPromptContent:
    """Assert Phase 48 prompt contains required analysis sections."""

    @pytest.fixture
    def prompt_content(self) -> str:
        """Read analyze-context-effectiveness prompt; skip if missing."""
        path = _analyze_context_effectiveness_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_includes_pre_analysis_checklist(self, prompt_content: str) -> None:
        """Prompt includes Pre-Analysis Checklist for recalling load_context calls."""
        assert "Pre-Analysis Checklist" in prompt_content
        assert "load_context" in prompt_content

    def test_includes_usage_analysis(self, prompt_content: str) -> None:
        """Prompt includes Usage Analysis (files used, missing, unused)."""
        assert "Usage Analysis" in prompt_content
        assert "files_read" in prompt_content or "files read" in prompt_content
        assert (
            "files_needed_but_missing" in prompt_content
            or "needed but missing" in prompt_content
        )

    def test_includes_scoring_metrics(self, prompt_content: str) -> None:
        """Prompt includes Scoring Metrics (precision, recall, F1, token efficiency)."""
        assert "Scoring Metrics" in prompt_content or "precision" in prompt_content
        assert "recall" in prompt_content
        assert "F1" in prompt_content or "f1_score" in prompt_content
        assert (
            "token" in prompt_content.lower() and "efficiency" in prompt_content.lower()
        )

    def test_includes_feedback_categories(self, prompt_content: str) -> None:
        """Prompt includes Feedback Categories (helpful, over_provisioned, etc.)."""
        assert "Feedback Categories" in prompt_content
        assert "helpful" in prompt_content
        assert "over_provisioned" in prompt_content
        assert "under_provisioned" in prompt_content

    def test_includes_feedback_schema_section(self, prompt_content: str) -> None:
        """Prompt includes Feedback Schema documentation for future MCP tool."""
        assert "Feedback Schema" in prompt_content
        assert (
            "record_context_feedback" in prompt_content or "feedback" in prompt_content
        )
