"""
Unit tests for roadmap_sync module.

Tests roadmap synchronization validation functionality.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.validation.roadmap_sync import (
    SyncValidationResult,
    parse_roadmap_references,
    scan_codebase_todos,
    validate_roadmap_sync,
)


class TestSyncValidationResult:
    """Tests for SyncValidationResult model defaults."""

    def test_completed_entries_in_roadmap_default_is_empty_list(self) -> None:
        """Default completed_entries_in_roadmap is empty list (typed factory)."""
        result = SyncValidationResult(valid=True, total_todos_found=0)
        assert result.completed_entries_in_roadmap == []


class TestValidateRoadmapSyncEnhancements:
    """Additional tests for roadmap synchronization enhancements."""

    def test_sync_result_includes_total_todos_found(self) -> None:
        """SyncValidationResult should report total_todos_found."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text("# TODO: Implement feature\n")

            roadmap_content = (
                "## Phase 1\n" + "See `src/module.py` for TODO implementation.\n"
            )

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is True
            assert result.total_todos_found == 1

    def test_validate_sync_resolves_plans_references_via_cortex_structure(self) -> None:
        """plans/ references should resolve via .cortex/plans."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cortex_dir = project_root / ".cortex"
            plans_dir = cortex_dir / "plans"
            plans_dir.mkdir(parents=True)
            plan_file = plans_dir / "phase-21-health-check-optimization.md"
            _ = plan_file.write_text("# Plan content\n")

            roadmap_content = (
                "## Phase 21\n"
                "See `../plans/phase-21-health-check-optimization.md` for details.\n"
            )

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is True
            assert len(result.invalid_references) == 0
            assert result.unlinked_plans == []

    def test_validate_sync_detects_unlinked_plans(self) -> None:
        """Validation fails when non-archived plans are not referenced in roadmap.md."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cortex_dir = project_root / ".cortex"
            plans_dir = cortex_dir / "plans"
            plans_dir.mkdir(parents=True)
            plan_file = plans_dir / "phase-68-investigate-fix-quality-issues.md"
            _ = plan_file.write_text("# Phase 68 plan\n")

            # Roadmap has no reference to the plan file
            roadmap_content = "## Blockers (ASAP Priority)\n\nNo entries yet.\n"

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is False
            assert result.missing_roadmap_entries == []
            assert result.invalid_references == []
            # Path is reported relative to project root
            assert str(plan_file.relative_to(project_root)) in result.unlinked_plans

    def test_validate_sync_resolves_dot_cortex_plans_archive_reference(self) -> None:
        """Archive PhaseX refs resolve to .cortex/plans (no path-style mismatch)."""
        # Arrange: layout is project_root/.cortex/plans/archive/Phase62/phase-62-foo.md
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            archive_dir = project_root / ".cortex" / "plans" / "archive" / "Phase62"
            archive_dir.mkdir(parents=True)
            plan_file = archive_dir / "phase-62-synapse-session-optimization.md"
            _ = plan_file.write_text("# Plan content\n")

            roadmap_content = (
                "## Phase 62\n"
                "Plan: `.cortex/plans/archive/Phase62/"
                "phase-62-synapse-session-optimization.md`.\n"
            )

            # Act: parse→cortex/plans/archive; resolver uses .cortex/plans
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert: valid, no invalid_references (path-style mismatch fixed)
            assert result.valid is True
            assert len(result.invalid_references) == 0

    def test_validate_sync_resolves_bare_memory_bank_md_reference(self) -> None:
        """Bare .md filenames (e.g. activeContext.md) resolve to .cortex/memory-bank."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            memory_bank_dir = project_root / ".cortex" / "memory-bank"
            memory_bank_dir.mkdir(parents=True)
            active_context = memory_bank_dir / "activeContext.md"
            _ = active_context.write_text("# Active Context\n")

            roadmap_content = (
                "Completed work is recorded in [activeContext.md](activeContext.md).\n"
            )

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is True
            assert len(result.invalid_references) == 0

    def test_validate_sync_fails_when_roadmap_contains_completed_entry(self) -> None:
        """Validation fails when roadmap contains a bullet that looks like completed work."""
        # Arrange: no TODOs; referenced plan exists so no invalid_refs; one completed bullet
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "src").mkdir()
            plans_dir = get_cortex_path(project_root, CortexResourceType.PLANS)
            archive_plan = (
                plans_dir / "archive" / "Phase18" / "phase-18-markdown-lint-fix-tool.md"
            )
            archive_plan.parent.mkdir(parents=True)
            _ = archive_plan.write_text("# Phase 18\n")
            roadmap_content = (
                "## Pending plans\n\n"
                "- **Phase 18: Markdown Lint Fix Tool** - COMPLETED (archived) - Plan: .cortex/plans/archive/Phase18/phase-18-markdown-lint-fix-tool.md.\n"
            )

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is False
            assert len(result.completed_entries_in_roadmap) == 1
            assert result.completed_entries_in_roadmap[0].line == 3
            assert "COMPLETED" in result.completed_entries_in_roadmap[0].snippet

    def test_validate_sync_passes_when_no_completed_entries(self) -> None:
        """Validation passes when roadmap has only pending-style bullets."""
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "src").mkdir()
            plans_dir = project_root / ".cortex" / "plans"
            plans_dir.mkdir(parents=True)
            _ = (plans_dir / "feature-x.md").write_text("# Feature X\n")
            _ = (plans_dir / "phase-49.md").write_text("# Phase 49\n")
            roadmap_content = (
                "## Pending plans\n\n"
                "- **Feature X** - PENDING - Plan: .cortex/plans/feature-x.md.\n"
                "- **Phase 49** - IN PROGRESS - Plan: .cortex/plans/phase-49.md.\n"
            )

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.completed_entries_in_roadmap == []


class TestFindCompletedEntriesInRoadmap:
    """Tests for completed-entries detection via validate_roadmap_sync."""

    def test_detects_completed_bullet(self) -> None:
        """Completed-style bullet is reported in completed_entries_in_roadmap."""
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "src").mkdir()
            content = (
                "## Section\n\n"
                "- **Phase 18** - COMPLETED (archived) - Plan: foo.md.\n"
            )
            result = validate_roadmap_sync(project_root, content)
            assert len(result.completed_entries_in_roadmap) == 1
            assert result.completed_entries_in_roadmap[0].line == 3
            assert "COMPLETED" in result.completed_entries_in_roadmap[0].snippet

    def test_detects_complete_bullet(self) -> None:
        """COMPLETE-style bullet is reported in completed_entries_in_roadmap."""
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "src").mkdir()
            content = "## Section\n\n- **Item** - COMPLETE - Done.\n"
            result = validate_roadmap_sync(project_root, content)
            assert len(result.completed_entries_in_roadmap) == 1
            assert result.completed_entries_in_roadmap[0].line == 3

    def test_ignores_pending_and_in_progress(self) -> None:
        """PENDING and IN PROGRESS bullets are not reported as completed."""
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "src").mkdir()
            content = (
                "## Section\n\n"
                "- **A** - PENDING - Plan: a.md.\n"
                "- **B** - IN PROGRESS - Plan: b.md.\n"
            )
            result = validate_roadmap_sync(project_root, content)
            assert result.completed_entries_in_roadmap == []

    def test_ignores_non_bullet_lines(self) -> None:
        """COMPLETED in non-bullet text is not reported."""
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "src").mkdir()
            content = "Text with COMPLETED word in a paragraph.\n"
            result = validate_roadmap_sync(project_root, content)
            assert result.completed_entries_in_roadmap == []


class TestScanCodebaseTodos:
    """Tests for scanning codebase for TODO markers."""

    def test_scan_todos_finds_python_todos(self):
        """Test scanning finds Python TODO comments."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text("# TODO: Implement feature\nprint('hello')\n")

            # Act
            todos = scan_codebase_todos(project_root)

            # Assert
            assert len(todos) == 1
            assert todos[0].file_path == "src/module.py"
            assert todos[0].line == 1
            assert "TODO" in todos[0].snippet
            assert todos[0].category == "todo"

    def test_scan_todos_finds_javascript_todos(self):
        """Test scanning finds JavaScript TODO comments."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "module.js"
            _ = prod_file.write_text("// TODO: Fix bug\nconsole.log('hello');\n")

            # Act
            todos = scan_codebase_todos(project_root)

            # Assert
            assert len(todos) == 1
            assert todos[0].file_path == "src/module.js"

    def test_scan_todos_excludes_test_files(self):
        """Test scanning excludes test files."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            test_file = src_dir / "test_file.py"
            _ = test_file.write_text("# TODO: This should be excluded\n")
            prod_file = src_dir / "production.py"
            _ = prod_file.write_text("# TODO: This should be included\n")

            # Act
            todos = scan_codebase_todos(project_root)

            # Assert
            assert len(todos) == 1  # Only production.py included, test_file excluded
            assert todos[0].file_path == "src/production.py"

    def test_scan_todos_excludes_example_files(self):
        """Test scanning excludes example files."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            example_file = src_dir / "example.py"
            _ = example_file.write_text("# TODO: This should be excluded\n")

            # Act
            todos = scan_codebase_todos(project_root)

            # Assert
            assert len(todos) == 0

    def test_scan_todos_finds_multiple_todos(self):
        """Test scanning finds multiple TODOs in same file."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text(
                "# TODO: First todo\n" + "print('hello')\n" + "# TODO: Second todo\n"
            )

            # Act
            todos = scan_codebase_todos(project_root)

            # Assert
            assert len(todos) == 2

    def test_scan_todos_scans_scripts_directory(self):
        """Test scanning includes scripts directory."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            scripts_dir = project_root / "scripts"
            _ = scripts_dir.mkdir()
            script_file = scripts_dir / "script.py"
            _ = script_file.write_text("# TODO: Script todo\n")

            # Act
            todos = scan_codebase_todos(project_root)

            # Assert
            assert len(todos) == 1
            assert todos[0].file_path == "scripts/script.py"


class TestParseRoadmapReferences:
    """Tests for parsing roadmap file references."""

    def test_parse_references_finds_file_paths(self):
        """Test parsing finds file path references."""
        # Arrange
        roadmap_content = "See `src/file.py` for details."

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 1
        assert references[0].file_path == "src/file.py"
        assert references[0].line is None

    def test_parse_references_finds_line_numbers(self):
        """Test parsing finds file path with line number."""
        # Arrange
        roadmap_content = "See `src/file.py:42` for details."

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 1
        assert references[0].file_path == "src/file.py"
        assert references[0].line == 42

    def test_parse_references_tracks_phase(self):
        """Test parsing tracks current phase context."""
        # Arrange
        roadmap_content = (
            "## Phase 1: Foundation\n"
            "See `src/file.py` for details.\n"
            "## Phase 2: Implementation\n"
            "See `src/other.py` for details.\n"
        )

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 2
        assert references[0].phase == "Phase 1: Foundation"
        assert references[1].phase == "Phase 2: Implementation"

    def test_parse_references_normalizes_paths(self):
        """Test parsing normalizes file paths."""
        # Arrange
        roadmap_content = "See `./src/file.py` or `../src/file.py` for details."

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 2
        assert references[0].file_path == "src/file.py"
        assert references[1].file_path == "src/file.py"

    def test_parse_references_finds_multiple_formats(self):
        """Test parsing finds various file format references."""
        # Arrange
        roadmap_content = "See `src/file.py`, `src/file.ts`, `src/file.go` for details."

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 3
        assert all(ref.file_path.endswith((".py", ".ts", ".go")) for ref in references)


class TestValidateRoadmapSync:
    """Tests for roadmap synchronization validation."""

    def test_validate_sync_all_todos_tracked(self):
        """Test validation passes when all TODOs are tracked."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text("# TODO: Implement feature\n")

            roadmap_content = (
                "## Phase 1\n" + "See `src/module.py` for TODO implementation.\n"
            )

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is True
            assert len(result.missing_roadmap_entries) == 0
            assert len(result.invalid_references) == 0

    def test_validate_sync_missing_todo_entry(self):
        """Test validation fails when TODO is not tracked."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text("# TODO: Untracked todo\n")

            roadmap_content = "## Phase 1\nNo reference to module.py\n"

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is False
            assert len(result.missing_roadmap_entries) == 1
            assert result.missing_roadmap_entries[0].file_path == "src/module.py"

    def test_validate_sync_invalid_reference(self):
        """Test validation fails when roadmap references missing file."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()

            roadmap_content = "See `src/missing.py` for details.\n"

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is False
            assert len(result.invalid_references) == 1
            assert result.invalid_references[0].file_path == "src/missing.py"

    def test_validate_sync_line_number_warning(self):
        """Test validation warns when line number exceeds file length."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text("line1\nline2\n")  # 2 lines

            roadmap_content = "See `src/module.py:100` for details.\n"

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is True  # Warning doesn't fail validation
            assert len(result.warnings) == 1
            assert "exceeds file length" in result.warnings[0]

    def test_validate_sync_valid_line_number(self):
        """Test validation passes when line number is valid."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text("line1\nline2\nline3\n")  # 3 lines

            roadmap_content = "See `src/module.py:2` for details.\n"

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is True
            assert len(result.warnings) == 0

    def test_validate_sync_multiple_issues(self):
        """Test validation detects multiple synchronization issues."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "untracked.py"
            _ = prod_file.write_text("# TODO: Untracked todo\n")
            other_file = src_dir / "other.py"
            _ = other_file.write_text(
                "line1\n"
            )  # Only 1 line, but roadmap references line 100

            roadmap_content = (
                "See `src/missing.py` for details.\n"
                + "See `src/other.py:100` for details.\n"
            )

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            assert result.valid is False
            assert len(result.missing_roadmap_entries) == 1
            assert len(result.invalid_references) == 1  # missing.py
            assert len(result.warnings) >= 1  # other.py:100 exceeds file length

    def test_validate_sync_file_matching_with_consistent_case(self):
        """Test validation matches files when casing is consistent."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            # Use consistent casing between file and roadmap reference
            prod_file = src_dir / "module.py"
            _ = prod_file.write_text("# TODO: Implement feature\n")

            roadmap_content = "See `src/module.py` for details.\n"

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            # The file "module.py" is matched because roadmap contains
            # "module.py" (same case)
            assert result.valid is True  # Matching case succeeds
            assert len(result.missing_roadmap_entries) == 0

    def test_validate_sync_no_ghost_phases(self):
        """Test validation does not report references from non-existent phases."""
        # Arrange: Roadmap without "Recent Findings" or "Completed Milestones" sections
        roadmap_content = (
            "# Roadmap\n\n"
            "## Blockers (ASAP Priority)\n\n"
            "- Some blocker.\n\n"
            "## Active Work\n\n"
            "- See `src/file.py` for details.\n\n"
            "## Future Enhancements\n\n"
            "- See `src/other.py` for details.\n"
        )

        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            file1 = src_dir / "file.py"
            _ = file1.write_text("# File content\n")
            file2 = src_dir / "other.py"
            _ = file2.write_text("# Other content\n")

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert: No references from ghost phases
            ghost_phases = ["Recent Findings", "Completed Milestones", "Planned Phases"]
            invalid_refs_from_ghost_phases = [
                ref for ref in result.invalid_references if ref.phase in ghost_phases
            ]
            assert (
                len(invalid_refs_from_ghost_phases) == 0
            ), f"Found {len(invalid_refs_from_ghost_phases)} invalid references from ghost phases: {invalid_refs_from_ghost_phases}"
            # Validation should pass since all references exist
            assert result.valid is True

    def test_validate_sync_filters_ghost_phase_references(self):
        """Test validation filters out references from ghost phases if they exist in content."""
        # Arrange: Roadmap with ghost sections (simulating reading from wrong file)
        roadmap_content = (
            "# Roadmap\n\n"
            "## Blockers (ASAP Priority)\n\n"
            "- Some blocker.\n\n"
            "## Recent Findings\n\n"
            "- See `src/ghost1.py` for details.\n\n"
            "## Completed Milestones\n\n"
            "- See `src/ghost2.py` for details.\n\n"
            "## Future Enhancements\n\n"
            "- See `src/valid.py` for details.\n"
        )

        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            valid_file = src_dir / "valid.py"
            _ = valid_file.write_text("# Valid content\n")

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert: References from ghost phases are filtered out
            ghost_phases = ["Recent Findings", "Completed Milestones", "Planned Phases"]
            invalid_refs_from_ghost_phases = [
                ref for ref in result.invalid_references if ref.phase in ghost_phases
            ]
            assert (
                len(invalid_refs_from_ghost_phases) == 0
            ), f"Found {len(invalid_refs_from_ghost_phases)} invalid references from ghost phases (should be filtered): {invalid_refs_from_ghost_phases}"
            # Only valid.py reference should be validated (and it exists, so no invalid refs)
            assert len(result.invalid_references) == 0
            assert result.valid is True
