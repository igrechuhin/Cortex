"""
Structural tests for the analyze feedback loop (post-prompt self-improvement).

Verifies:
1. All 8 caller prompts reference post-prompt-hook.md (no missing hook steps).
2. analyze.md has Steps 9a (Skill Router), 9b (Plan Router), 9c (Rule Router).
3. post-prompt-hook.md exists and does NOT recursively reference itself or
   directly invoke analyze.md (no circular reference).
4. prompts-manifest.json (synapse) includes post-prompt-hook entry.
5. No caller prompt contains the misleading recursion-guard text (guard must
   live only in post-prompt-hook.md).

Plan reference: .cortex/plans/analyze-feedback-loop.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return get_project_root()


def _synapse_prompts_dir() -> Path:
    return get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE) / "prompts"


def _cortex_prompts_dir() -> Path:
    return _repo_root() / ".cortex" / "prompts"


def _read(path: Path) -> str:
    if not path.exists():
        pytest.skip(f"(ref: cleanup-skipped-legacy-tests) file not found at {path}")
    return path.read_text()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# All prompts that must invoke post-prompt-hook.md (excludes analyze.md and
# post-prompt-hook.md itself).
_SYNAPSE_CALLER_PROMPTS: tuple[str, ...] = (
    "commit.md",
    "fix.md",
    "review.md",
    "plan.md",
    "do.md",
)

_CORTEX_CALLER_PROMPTS: tuple[str, ...] = (
    "debug-external-integration.md",
    "populate-tiktoken-cache.md",
    "validate-roadmap-sync.md",
)

_HOOK_FILE = "post-prompt-hook.md"
_HOOK_REF = "post-prompt-hook.md"

# Recursion-guard text that must NOT appear in caller prompts (it belongs only
# in post-prompt-hook.md itself).
_STALE_GUARD_FRAGMENT = "Guard against recursion"


# ---------------------------------------------------------------------------
# 1. All caller prompts invoke the post-prompt hook
# ---------------------------------------------------------------------------


class TestCallerPromptsInvokeHook:
    """Every caller prompt must reference post-prompt-hook.md."""

    @pytest.mark.parametrize("filename", _SYNAPSE_CALLER_PROMPTS)
    def test_synapse_prompt_invokes_hook(self, filename: str) -> None:
        path = _synapse_prompts_dir() / filename
        content = _read(path)
        assert _HOOK_REF in content, (
            f"{filename} does not reference {_HOOK_REF}; "
            "add a Post-Prompt Hook step before ## Final report"
        )

    @pytest.mark.parametrize("filename", _CORTEX_CALLER_PROMPTS)
    def test_cortex_prompt_invokes_hook(self, filename: str) -> None:
        path = _cortex_prompts_dir() / filename
        content = _read(path)
        assert _HOOK_REF in content, (
            f"{filename} does not reference {_HOOK_REF}; "
            "add a Post-Prompt Hook step before completion"
        )


# ---------------------------------------------------------------------------
# 2. analyze.md has the three-way router (Steps 9a / 9b / 9c)
# ---------------------------------------------------------------------------


class TestAnalyzePromptRouter:
    """analyze.md must contain all three router steps."""

    @pytest.fixture
    def analyze_content(self) -> str:
        return _read(_synapse_prompts_dir() / "analyze.md")

    def test_skill_router_present(self, analyze_content: str) -> None:
        assert (
            "Skill Router" in analyze_content
        ), "analyze.md is missing Step 9a (Skill Router)"

    def test_plan_router_present(self, analyze_content: str) -> None:
        assert (
            "Plan Router" in analyze_content
        ), "analyze.md is missing Step 9b (Plan Router)"

    def test_rule_router_present(self, analyze_content: str) -> None:
        assert (
            "Rule Router" in analyze_content
        ), "analyze.md is missing Step 9c (Rule Router)"

    def test_router_steps_ordered(self, analyze_content: str) -> None:
        """9a, 9b, 9c appear in ascending order in the file."""
        skill_pos = analyze_content.index("Skill Router")
        plan_pos = analyze_content.index("Plan Router")
        rule_pos = analyze_content.index("Rule Router")
        assert (
            skill_pos < plan_pos < rule_pos
        ), "analyze.md router steps are not in order (9a < 9b < 9c)"

    def test_router_skill_path_hint(self, analyze_content: str) -> None:
        """Skill Router references the skills resource directory."""
        assert (
            ".cortex/resources/skills" in analyze_content
        ), "analyze.md Step 9a should reference .cortex/resources/skills/"

    def test_router_rule_path_hint(self, analyze_content: str) -> None:
        """Rule Router references the synapse rules directory."""
        assert (
            ".cortex/synapse/rules" in analyze_content
        ), "analyze.md Step 9c should reference .cortex/synapse/rules/"


# ---------------------------------------------------------------------------
# 3. post-prompt-hook.md: exists, has recursion guard, no circular reference
# ---------------------------------------------------------------------------


class TestPostPromptHookFile:
    """post-prompt-hook.md must have guard and must not reference itself."""

    @pytest.fixture
    def hook_content(self) -> str:
        return _read(_synapse_prompts_dir() / _HOOK_FILE)

    def test_hook_file_exists(self) -> None:
        path = _synapse_prompts_dir() / _HOOK_FILE
        assert path.exists(), f"{_HOOK_FILE} does not exist under synapse/prompts/"

    def test_hook_has_caller_guard(self, hook_content: str) -> None:
        """Hook must skip execution when caller is /cortex/analyze."""
        lower = hook_content.lower()
        assert (
            "/cortex/analyze" in hook_content or "analyze.md" in hook_content
        ), f"{_HOOK_FILE} missing caller guard referencing /cortex/analyze"
        assert (
            "skip" in lower or "guard" in lower
        ), f"{_HOOK_FILE} missing skip/guard instruction in caller guard section"

    def test_hook_does_not_invoke_itself(self, hook_content: str) -> None:
        """post-prompt-hook.md must not reference itself to prevent self-recursion."""
        # The file header may contain the filename, so check for invocation patterns
        # (e.g. "Read `.cortex/synapse/prompts/post-prompt-hook.md`") rather than
        # any occurrence of the filename.
        invocation_pattern = "Read `.cortex/synapse/prompts/post-prompt-hook.md`"
        assert (
            invocation_pattern not in hook_content
        ), f"{_HOOK_FILE} invokes itself — circular self-reference detected"

    def test_hook_does_not_invoke_analyze(self, hook_content: str) -> None:
        """post-prompt-hook.md must not directly invoke analyze.md as a sub-prompt."""
        invocation_pattern = "Read `.cortex/synapse/prompts/analyze.md`"
        assert invocation_pattern not in hook_content, (
            f"{_HOOK_FILE} directly invokes analyze.md — this would create a "
            "circular loop (analyze → hook → analyze)"
        )

    def test_hook_has_improvements_router(self, hook_content: str) -> None:
        """Hook must contain a router step for Skills/Plans/Rules."""
        assert (
            "Router" in hook_content or "router" in hook_content
        ), f"{_HOOK_FILE} missing Improvements Router step (Step 9)"

    def test_hook_has_artifact_summary_table(self, hook_content: str) -> None:
        """Hook must produce a minimal artifact summary table."""
        assert (
            "Post-Prompt Hook Result" in hook_content
        ), f"{_HOOK_FILE} missing ## Post-Prompt Hook Result artifact summary table"


# ---------------------------------------------------------------------------
# 4. prompts-manifest.json includes post-prompt-hook entry
# ---------------------------------------------------------------------------


class TestPromptManifestHookEntry:
    """Synapse prompts-manifest.json must register post-prompt-hook.md."""

    @pytest.fixture
    def manifest_data(self) -> dict[str, object]:
        path = _synapse_prompts_dir() / "prompts-manifest.json"
        if not path.exists():
            pytest.skip(
                f"(ref: cleanup-skipped-legacy-tests) manifest not found at {path}"
            )
        data: object = json.loads(path.read_text())
        assert isinstance(data, dict), "prompts-manifest.json is not a JSON object"
        return cast(dict[str, object], data)

    def _all_prompt_entries(
        self, manifest_data: dict[str, object]
    ) -> list[dict[str, object]]:
        categories = manifest_data.get("categories")
        if not isinstance(categories, dict):
            return []
        entries: list[dict[str, object]] = []
        for section in cast(dict[str, object], categories).values():
            if not isinstance(section, dict):
                continue
            prompts_val = cast(dict[str, object], section).get("prompts")
            if isinstance(prompts_val, list):
                entries.extend(
                    cast(dict[str, object], p)
                    for p in cast(list[object], prompts_val)
                    if isinstance(p, dict)
                )
        return entries

    def test_hook_listed_in_manifest(self, manifest_data: dict[str, object]) -> None:
        entries = self._all_prompt_entries(manifest_data)
        files = [str(e.get("file", "")) for e in entries]
        assert (
            _HOOK_FILE in files
        ), f"{_HOOK_FILE} is not registered in prompts-manifest.json"

    def test_hook_entry_has_name_and_description(
        self, manifest_data: dict[str, object]
    ) -> None:
        entries = self._all_prompt_entries(manifest_data)
        entry = next((e for e in entries if e.get("file") == _HOOK_FILE), None)
        assert entry is not None, f"No manifest entry for {_HOOK_FILE}"
        assert "name" in entry, f"{_HOOK_FILE} manifest entry missing 'name'"
        assert (
            "description" in entry
        ), f"{_HOOK_FILE} manifest entry missing 'description'"


# ---------------------------------------------------------------------------
# 5. No caller prompt contains stale recursion-guard copy-paste
# ---------------------------------------------------------------------------


class TestNoStaleRecursionGuardInCallers:
    """Callers must not contain the old copy-pasted recursion guard text."""

    @pytest.mark.parametrize("filename", _SYNAPSE_CALLER_PROMPTS)
    def test_synapse_caller_no_stale_guard(self, filename: str) -> None:
        path = _synapse_prompts_dir() / filename
        content = _read(path)
        assert _STALE_GUARD_FRAGMENT not in content, (
            f"{filename} still contains stale recursion guard text "
            f"'{_STALE_GUARD_FRAGMENT}'; remove it — the guard belongs only in "
            f"{_HOOK_FILE}"
        )

    @pytest.mark.parametrize("filename", _CORTEX_CALLER_PROMPTS)
    def test_cortex_caller_no_stale_guard(self, filename: str) -> None:
        path = _cortex_prompts_dir() / filename
        content = _read(path)
        assert _STALE_GUARD_FRAGMENT not in content, (
            f"{filename} still contains stale recursion guard text "
            f"'{_STALE_GUARD_FRAGMENT}'; remove it — the guard belongs only in "
            f"{_HOOK_FILE}"
        )
