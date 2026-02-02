"""
Integration tests for unified Analyze (end-of-session) prompt.

Verifies that analyze.md is the single end-of-session prompt in the manifest
and contains required sections: Pre-Analysis Checklist, context effectiveness,
session optimization, and unified output format. Replaces the former
analyze-context-effectiveness and analyze-session-optimization prompts.
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


def _analyze_prompt_path() -> Path:
    """Return path to unified analyze prompt."""
    return _prompts_dir() / "analyze.md"


def _manifest_path() -> Path:
    """Return path to prompts-manifest.json."""
    return _prompts_dir() / "prompts-manifest.json"


class TestUnifiedAnalyzeInManifest:
    """Assert unified analyze.md is the single analyze prompt in manifest."""

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

    def test_analyze_listed_in_manifest(
        self, manifest_data: dict[str, object] | None
    ) -> None:
        """Manifest general category includes exactly one analyze prompt (analyze.md)."""
        assert manifest_data is not None
        prompts = _get_prompts_from_manifest(manifest_data)
        files = [str(p.get("file", "")) for p in prompts]
        assert "analyze.md" in files
        assert "analyze-context-effectiveness.md" not in files
        assert "analyze-session-optimization.md" not in files

    def test_analyze_has_name_and_description(
        self, manifest_data: dict[str, object] | None
    ) -> None:
        """Analyze entry has name and description for end-of-session check-all."""
        assert manifest_data is not None
        prompts = _get_prompts_from_manifest(manifest_data)
        entry = next(
            (p for p in prompts if p.get("file") == "analyze.md"),
            None,
        )
        assert entry is not None
        assert "name" in entry and "description" in entry
        desc = entry.get("description")
        desc_str = desc if isinstance(desc, str) else ""
        assert "context" in desc_str.lower() or "effectiveness" in desc_str.lower()
        assert "session" in desc_str.lower() or "optimization" in desc_str.lower()


class TestUnifiedAnalyzePromptContent:
    """Assert unified analyze prompt contains required analysis sections."""

    @pytest.fixture
    def prompt_content(self) -> str:
        """Read unified analyze prompt; skip if missing."""
        path = _analyze_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_includes_pre_analysis_checklist(self, prompt_content: str) -> None:
        """Prompt includes Pre-Analysis Checklist (memory bank, rules, context recall)."""
        assert "Pre-Analysis Checklist" in prompt_content
        assert "load_context" in prompt_content

    def test_includes_context_effectiveness_step(self, prompt_content: str) -> None:
        """Prompt includes Step 1: Context effectiveness (tool + no_data handling)."""
        assert "Context Effectiveness" in prompt_content
        assert "analyze_context_effectiveness" in prompt_content
        assert "no_data" in prompt_content or "no data" in prompt_content

    def test_includes_session_optimization_step(self, prompt_content: str) -> None:
        """Prompt includes Step 2: Session optimization (mistake patterns, report save)."""
        assert "Session Optimization" in prompt_content
        assert "get_structure_info" in prompt_content
        assert "reviews" in prompt_content

    def test_includes_unified_output_format(self, prompt_content: str) -> None:
        """Prompt includes unified output format (Context + Session sections)."""
        assert "Output Format" in prompt_content or "output format" in prompt_content
        assert "Context Effectiveness Analysis" in prompt_content
        assert "Session Optimization Analysis" in prompt_content

    def test_includes_usage_analysis_or_scoring(self, prompt_content: str) -> None:
        """Prompt includes usage/scoring concepts for manual fallback."""
        assert "precision" in prompt_content or "recall" in prompt_content
        assert "feedback" in prompt_content.lower() or "utilization" in prompt_content
