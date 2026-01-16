"""
Unit tests for roadmap_sync module.

Tests roadmap synchronization validation functionality.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from cortex.validation.roadmap_sync import (
    parse_roadmap_references,
    scan_codebase_todos,
    validate_roadmap_sync,
)


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
            assert todos[0]["file_path"] == "src/module.py"
            assert todos[0]["line"] == 1
            assert "TODO" in todos[0]["snippet"]
            assert todos[0]["category"] == "todo"

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
            assert todos[0]["file_path"] == "src/module.js"

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
            assert todos[0]["file_path"] == "src/production.py"

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
            assert todos[0]["file_path"] == "scripts/script.py"


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
        assert references[0]["file_path"] == "src/file.py"
        assert references[0]["line"] is None

    def test_parse_references_finds_line_numbers(self):
        """Test parsing finds file path with line number."""
        # Arrange
        roadmap_content = "See `src/file.py:42` for details."

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 1
        assert references[0]["file_path"] == "src/file.py"
        assert references[0]["line"] == 42

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
        assert references[0]["phase"] == "Phase 1: Foundation"
        assert references[1]["phase"] == "Phase 2: Implementation"

    def test_parse_references_normalizes_paths(self):
        """Test parsing normalizes file paths."""
        # Arrange
        roadmap_content = "See `./src/file.py` or `../src/file.py` for details."

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 2
        assert references[0]["file_path"] == "src/file.py"
        assert references[1]["file_path"] == "src/file.py"

    def test_parse_references_finds_multiple_formats(self):
        """Test parsing finds various file format references."""
        # Arrange
        roadmap_content = "See `src/file.py`, `src/file.ts`, `src/file.go` for details."

        # Act
        references = parse_roadmap_references(roadmap_content)

        # Assert
        assert len(references) == 3
        assert all(
            ref["file_path"].endswith((".py", ".ts", ".go")) for ref in references
        )


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
            assert result["valid"] is True
            assert len(result["missing_roadmap_entries"]) == 0
            assert len(result["invalid_references"]) == 0

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
            assert result["valid"] is False
            assert len(result["missing_roadmap_entries"]) == 1
            assert result["missing_roadmap_entries"][0]["file_path"] == "src/module.py"

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
            assert result["valid"] is False
            assert len(result["invalid_references"]) == 1
            assert result["invalid_references"][0]["file_path"] == "src/missing.py"

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
            assert result["valid"] is True  # Warning doesn't fail validation
            assert len(result["warnings"]) == 1
            assert "exceeds file length" in result["warnings"][0]

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
            assert result["valid"] is True
            assert len(result["warnings"]) == 0

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
            assert result["valid"] is False
            assert len(result["missing_roadmap_entries"]) == 1
            assert len(result["invalid_references"]) == 1  # missing.py
            assert len(result["warnings"]) >= 1  # other.py:100 exceeds file length

    def test_validate_sync_case_sensitive_file_matching(self):
        """Test validation uses case-insensitive file matching for TODO tracking."""
        # Arrange
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            _ = src_dir.mkdir()
            prod_file = src_dir / "Module.py"
            _ = prod_file.write_text("# TODO: Implement feature\n")

            roadmap_content = "See `src/module.py` for details.\n"

            # Act
            result = validate_roadmap_sync(project_root, roadmap_content)

            # Assert
            # Note: Current implementation uses case-insensitive matching (lowercase comparison)
            # The file "Module.py" is matched because roadmap contains "module.py" (lowercase)
            assert result["valid"] is True  # Case-insensitive match succeeds
            assert len(result["missing_roadmap_entries"]) == 0
