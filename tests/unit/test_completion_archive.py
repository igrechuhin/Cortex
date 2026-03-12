"""Tests for completion_archive: remove_roadmap_entry_for_plan and archive_plan_file."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.plans.completion_archive import (
    archive_plan_file,
    archive_subdir_for_plan,
    remove_roadmap_entry_for_plan,
)

# ---------------------------------------------------------------------------
# remove_roadmap_entry_for_plan
# ---------------------------------------------------------------------------


class TestRemoveRoadmapEntryForPlan:
    def test_removes_bullet_with_pipe_ref(self) -> None:
        content = (
            "- **[MED-10] Title** — desc. Plan: `plans/my-plan.md` | Priority: High\n"
            "- **[X] Other** — keep me\n"
        )
        result = remove_roadmap_entry_for_plan(content, "my-plan.md")
        assert "my-plan.md" not in result
        assert "MED-10" not in result
        assert "Other" in result

    def test_removes_bullet_at_end_of_file(self) -> None:
        content = "- **[X] Title** — desc. Plan: `plans/foo.md`\n"
        result = remove_roadmap_entry_for_plan(content, "foo.md")
        assert result.strip() == ""

    def test_no_match_returns_unchanged(self) -> None:
        content = "- **[X] Title** — no plan ref here\n"
        result = remove_roadmap_entry_for_plan(content, "foo.md")
        assert result == content

    def test_does_not_touch_other_plan_refs(self) -> None:
        content = (
            "- **[A]** Plan: `plans/a.md` | Priority: Low\n"
            "- **[B]** Plan: `plans/b.md` | Priority: Med\n"
        )
        result = remove_roadmap_entry_for_plan(content, "a.md")
        assert "plans/a.md" not in result
        assert "[A]" not in result
        assert "plans/b.md" in result
        assert "[B]" in result

    def test_case_insensitive(self) -> None:
        content = "- **[X]** PLAN: `plans/My-Plan.md` | Order: 1\n"
        result = remove_roadmap_entry_for_plan(content, "My-Plan.md")
        assert "My-Plan.md" not in result
        assert "[X]" not in result


# ---------------------------------------------------------------------------
# archive_subdir_for_plan
# ---------------------------------------------------------------------------


class TestArchiveSubdirForPlan:
    def test_phase_plan(self) -> None:
        assert archive_subdir_for_plan("phase-42-foo.md") == "Phase42"

    def test_session_optimization(self) -> None:
        assert (
            archive_subdir_for_plan("session-optimization-2026.md")
            == "SessionOptimization"
        )

    def test_investigation_with_date(self) -> None:
        assert (
            archive_subdir_for_plan("investigate-bug-20260101.md")
            == "Investigations/2026-01-01"
        )

    def test_investigation_without_date(self) -> None:
        assert archive_subdir_for_plan("investigate-something.md") == "Investigations"

    def test_other_plan(self) -> None:
        assert archive_subdir_for_plan("make-prompts-agent-agnostic.md") == "Other"

    def test_path_components_rejected(self) -> None:
        assert archive_subdir_for_plan("sub/plan.md") is None


# ---------------------------------------------------------------------------
# archive_plan_file: roadmap entry is removed after archiving
# ---------------------------------------------------------------------------


class TestArchivePlanFileRemovesRoadmapEntry:
    def _make_tree(self, tmp_path: Path, plan_name: str, roadmap_content: str) -> Path:
        """Create minimal cortex directory tree and return project root."""
        root = tmp_path / "project"
        plans_dir = root / ".cortex" / "plans"
        plans_dir.mkdir(parents=True)
        _ = (plans_dir / plan_name).write_text(
            "# Plan\nstatus: COMPLETE\n", encoding="utf-8"
        )
        mem_dir = root / ".cortex" / "memory-bank"
        mem_dir.mkdir(parents=True)
        _ = (mem_dir / "roadmap.md").write_text(roadmap_content, encoding="utf-8")
        (root / ".cortex" / "plans" / "archive").mkdir(parents=True)
        return root

    def test_removes_roadmap_entry_after_archive(self, tmp_path: Path) -> None:
        plan = "my-plan.md"
        roadmap = (
            "- **[X] Title** Plan: `plans/my-plan.md` | Priority: Low\n"
            "- **[Y] Keep** Plan: `plans/other.md` | Priority: Low\n"
        )
        root = self._make_tree(tmp_path, plan, roadmap)

        archive_path, err = archive_plan_file(root, plan)

        assert err is None
        assert archive_path is not None
        roadmap_after = (root / ".cortex" / "memory-bank" / "roadmap.md").read_text()
        assert "my-plan.md" not in roadmap_after
        assert "[X]" not in roadmap_after
        assert "[Y]" in roadmap_after

    def test_archive_failure_leaves_roadmap_unchanged(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        plans_dir = root / ".cortex" / "plans"
        plans_dir.mkdir(parents=True)
        mem_dir = root / ".cortex" / "memory-bank"
        mem_dir.mkdir(parents=True)
        original = "- **[X]** Plan: `plans/ghost.md`\n"
        _ = (mem_dir / "roadmap.md").write_text(original, encoding="utf-8")

        _, err = archive_plan_file(root, "ghost.md")

        assert err is not None
        assert (mem_dir / "roadmap.md").read_text() == original
