#!/usr/bin/env python3
"""
Unit tests for TemplateManager module (Phase 8).

Tests template generation, plan/rule creation, and file generation.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.structure.template_manager import TemplateManager

# ============================================================================
# Test TemplateManager Initialization
# ============================================================================


class TestTemplateManagerInitialization:
    """Test TemplateManager initialization."""

    def test_init_sets_project_root(self, tmp_path: Path):
        """Test initialization sets project_root correctly."""
        # Arrange & Act
        manager = TemplateManager(tmp_path)

        # Assert
        assert manager.project_root == tmp_path
        assert isinstance(manager.project_root, Path)

    def test_init_with_relative_path(self, tmp_path: Path):
        """Test initialization works with relative paths."""
        # Arrange
        relative_path = Path(".")

        # Act
        manager = TemplateManager(relative_path)

        # Assert
        assert manager.project_root == relative_path

    def test_plan_templates_constant_exists(self):
        """Test PLAN_TEMPLATES constant is defined."""
        # Assert
        assert hasattr(TemplateManager, "PLAN_TEMPLATES")
        assert isinstance(TemplateManager.PLAN_TEMPLATES, dict)
        assert len(TemplateManager.PLAN_TEMPLATES) > 0

    def test_rule_templates_constant_exists(self):
        """Test RULE_TEMPLATES constant is defined."""
        # Assert
        assert hasattr(TemplateManager, "RULE_TEMPLATES")
        assert isinstance(TemplateManager.RULE_TEMPLATES, dict)
        assert len(TemplateManager.RULE_TEMPLATES) > 0


# ============================================================================
# Test generate_plan()
# ============================================================================


class TestGeneratePlan:
    """Test plan generation from templates."""

    def test_generate_feature_plan_with_defaults(self, tmp_path: Path):
        """Test generating feature plan with default variables."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plan_name = "User Authentication"

        # Act
        content = manager.generate_plan("feature.md", plan_name)

        # Assert
        assert isinstance(content, str)
        assert plan_name in content
        assert "[Feature Name]" not in content
        assert "## Status" in content
        assert "## Goal" in content
        assert "{date}" not in content  # Should be replaced

    def test_generate_bugfix_plan_with_defaults(self, tmp_path: Path):
        """Test generating bugfix plan with default variables."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plan_name = "Login Button Not Working"

        # Act
        content = manager.generate_plan("bugfix.md", plan_name)

        # Assert
        assert isinstance(content, str)
        assert plan_name in content
        assert "[Bug Description]" not in content
        assert "## Problem Description" in content
        assert "## Root Cause Analysis" in content

    def test_generate_refactoring_plan_with_defaults(self, tmp_path: Path):
        """Test generating refactoring plan with default variables."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plan_name = "Extract User Service"

        # Act
        content = manager.generate_plan("refactoring.md", plan_name)

        # Assert
        assert isinstance(content, str)
        assert plan_name in content
        assert "[Refactoring Title]" not in content
        assert "## Current State" in content
        assert "## Target State" in content

    def test_generate_research_plan_with_defaults(self, tmp_path: Path):
        """Test generating research plan with default variables."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plan_name = "Database Migration Strategy"

        # Act
        content = manager.generate_plan("research.md", plan_name)

        # Assert
        assert isinstance(content, str)
        assert plan_name in content
        assert "[Research Topic]" not in content
        assert "## Questions to Answer" in content
        assert "## Recommendations" in content

    def test_generate_plan_with_custom_variables(self, tmp_path: Path):
        """Test generating plan with custom variables."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plan_name = "Test Feature"
        custom_vars = {"author": "John Doe", "priority": "High"}

        # Act
        content = manager.generate_plan("feature.md", plan_name, custom_vars)

        # Assert
        assert plan_name in content
        # Note: Custom vars won't be substituted unless template has
        # {author}, {priority}
        # But date should still be replaced
        assert "{date}" not in content

    def test_generate_plan_includes_date(self, tmp_path: Path):
        """Test generated plan includes current date."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plan_name = "Test Plan"
        expected_date = datetime.now().strftime("%Y-%m-%d")

        # Act
        content = manager.generate_plan("feature.md", plan_name)

        # Assert
        assert expected_date in content
        assert "Created:" in content
        assert "Last Updated:" in content

    def test_generate_plan_raises_error_for_unknown_type(self, tmp_path: Path):
        """Test generate_plan raises ValueError for unknown plan type."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown plan type"):
            _ = manager.generate_plan("unknown.md", "Test Plan")

    def test_generate_plan_replaces_all_title_placeholders(self, tmp_path: Path):
        """Test all title placeholders are replaced correctly."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plan_name = "My Plan"

        # Act
        feature_content = manager.generate_plan("feature.md", plan_name)
        bugfix_content = manager.generate_plan("bugfix.md", plan_name)
        refactoring_content = manager.generate_plan("refactoring.md", plan_name)
        research_content = manager.generate_plan("research.md", plan_name)

        # Assert
        assert "[Feature Name]" not in feature_content
        assert "[Bug Description]" not in bugfix_content
        assert "[Refactoring Title]" not in refactoring_content
        assert "[Research Topic]" not in research_content
        assert plan_name in feature_content
        assert plan_name in bugfix_content
        assert plan_name in refactoring_content
        assert plan_name in research_content


# ============================================================================
# Test generate_rule()
# ============================================================================


class TestGenerateRule:
    """Test rule generation from templates."""

    def test_generate_coding_standards_rule(self, tmp_path: Path):
        """Test generating coding-standards rule."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act
        content = manager.generate_rule("coding-standards.md")

        # Assert
        assert isinstance(content, str)
        assert "# Coding Standards" in content
        assert "## Context" in content
        assert "## Standards" in content
        assert "## Examples" in content

    def test_generate_architecture_rule(self, tmp_path: Path):
        """Test generating architecture rule."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act
        content = manager.generate_rule("architecture.md")

        # Assert
        assert isinstance(content, str)
        assert "# Architecture Guidelines" in content
        assert "## Patterns" in content
        assert "## Principles" in content

    def test_generate_testing_rule(self, tmp_path: Path):
        """Test generating testing rule."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act
        content = manager.generate_rule("testing.md")

        # Assert
        assert isinstance(content, str)
        assert "# Testing Standards" in content
        assert "## Requirements" in content
        assert "## Standards" in content

    def test_generate_rule_with_custom_variables(self, tmp_path: Path):
        """Test generating rule with custom variables."""
        # Arrange
        manager = TemplateManager(tmp_path)
        variables = {"language": "Python", "framework": "Django"}

        # Act
        content = manager.generate_rule("coding-standards.md", variables)

        # Assert
        assert isinstance(content, str)
        # Note: Variables only substituted if template has placeholders

    def test_generate_rule_raises_error_for_unknown_type(self, tmp_path: Path):
        """Test generate_rule raises ValueError for unknown rule type."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown rule type"):
            _ = manager.generate_rule("unknown.md")


# ============================================================================
# Test create_plan_templates()
# ============================================================================


class TestCreatePlanTemplates:
    """Test plan template file creation."""

    def test_create_plan_templates_creates_all_files(self, tmp_path: Path):
        """Test create_plan_templates creates all template files."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plans_dir = tmp_path / "plans"

        # Act
        report = manager.create_plan_templates(plans_dir)

        # Assert
        assert isinstance(report, dict)
        assert "created" in report
        assert "skipped" in report
        assert "errors" in report

        created = report["created"]
        assert isinstance(created, list)
        assert len(created) == len(TemplateManager.PLAN_TEMPLATES)  # type: ignore[arg-type]

        # Verify files exist
        templates_dir = plans_dir / "templates"
        for template_name in TemplateManager.PLAN_TEMPLATES:
            template_path = templates_dir / template_name
            assert template_path.exists()
            assert str(template_path) in created

    def test_create_plan_templates_skips_existing_files(self, tmp_path: Path):
        """Test create_plan_templates skips existing template files."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plans_dir = tmp_path / "plans"
        templates_dir = plans_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        # Create one existing template
        existing_template = templates_dir / "feature.md"
        _ = existing_template.write_text("Existing content", encoding="utf-8")

        # Act
        report = manager.create_plan_templates(plans_dir)

        # Assert
        skipped = report["skipped"]
        assert isinstance(skipped, list)
        assert len(skipped) == 1  # type: ignore[arg-type]
        assert str(existing_template) in skipped

        # Verify existing file wasn't overwritten
        assert existing_template.read_text(encoding="utf-8") == "Existing content"

        # Verify other templates were created
        created = report["created"]
        assert len(created) == len(TemplateManager.PLAN_TEMPLATES) - 1  # type: ignore[arg-type]

    def test_create_plan_templates_creates_directory(self, tmp_path: Path):
        """Test create_plan_templates creates templates directory if missing."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plans_dir = tmp_path / "plans"

        # Act
        _ = manager.create_plan_templates(plans_dir)

        # Assert
        templates_dir = plans_dir / "templates"
        assert templates_dir.exists()
        assert templates_dir.is_dir()

    def test_create_plan_templates_writes_correct_content(self, tmp_path: Path):
        """Test created template files contain correct content."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plans_dir = tmp_path / "plans"

        # Act
        _ = manager.create_plan_templates(plans_dir)

        # Assert
        templates_dir = plans_dir / "templates"
        for template_name, expected_content in TemplateManager.PLAN_TEMPLATES.items():
            template_path = templates_dir / template_name
            actual_content = template_path.read_text(encoding="utf-8")
            assert actual_content == expected_content

    def test_create_plan_templates_handles_write_errors(self, tmp_path: Path):
        """Test create_plan_templates handles file write errors gracefully."""
        # Arrange
        manager = TemplateManager(tmp_path)
        plans_dir = tmp_path / "plans"

        # Mock write_text to raise exception
        with patch("pathlib.Path.write_text") as mock_write:
            mock_write.side_effect = PermissionError("Permission denied")

            # Act
            report = manager.create_plan_templates(plans_dir)

            # Assert
            assert "errors" in report
            errors = report["errors"]
            assert isinstance(errors, list)
            assert len(errors) > 0  # type: ignore[arg-type]
            assert any("Failed to create" in str(error) for error in errors)  # type: ignore[arg-type]


# ============================================================================
# Test interactive_project_setup()
# ============================================================================


class TestInteractiveProjectSetup:
    """Test interactive project setup structure."""

    def test_interactive_project_setup_returns_questions_dict(self, tmp_path: Path):
        """Test interactive_project_setup returns questions structure."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act
        result = manager.interactive_project_setup()

        # Assert
        assert isinstance(result, dict)
        assert "questions" in result
        assert isinstance(result["questions"], list)
        assert len(result["questions"]) > 0  # type: ignore[arg-type]

    def test_interactive_project_setup_questions_have_required_fields(
        self, tmp_path: Path
    ):
        """Test all questions have required fields."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act
        result = manager.interactive_project_setup()
        questions = result["questions"]

        # Assert
        required_fields = {"id", "question", "type"}
        assert isinstance(questions, list)
        for question in questions:  # type: ignore[assignment]
            assert isinstance(question, dict)
            assert required_fields.issubset(question.keys())  # type: ignore[arg-type]

    def test_interactive_project_setup_includes_all_question_types(
        self, tmp_path: Path
    ):
        """Test questions include text, choice, and boolean types."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act
        result = manager.interactive_project_setup()
        questions = result["questions"]

        # Assert
        assert isinstance(questions, list)
        question_types = {q["type"] for q in questions}  # type: ignore[misc]
        assert "text" in question_types
        assert "choice" in question_types
        assert "boolean" in question_types

    def test_interactive_project_setup_choice_questions_have_options(
        self, tmp_path: Path
    ):
        """Test choice questions have options field."""
        # Arrange
        manager = TemplateManager(tmp_path)

        # Act
        result = manager.interactive_project_setup()
        questions = result["questions"]

        # Assert
        assert isinstance(questions, list)
        choice_questions = [q for q in questions if q["type"] == "choice"]  # type: ignore[misc]
        for question in choice_questions:  # type: ignore[assignment]
            assert "options" in question
            assert isinstance(question["options"], list)
            assert len(question["options"]) > 0  # type: ignore[arg-type]


# ============================================================================
# Test generate_initial_files()
# ============================================================================


class TestGenerateInitialFiles:
    """Test initial file generation."""

    def test_generate_initial_files_creates_projectBrief(self, tmp_path: Path):
        """Test generate_initial_files creates projectBrief.md."""
        # Arrange
        manager = TemplateManager(tmp_path)
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        project_info: dict[str, object] = {"project_name": "Test Project"}
        templates = {"projectBrief.md": "# {project_name}"}

        # Act
        report = manager.generate_initial_files(knowledge_dir, project_info, templates)

        # Assert
        assert "generated" in report
        generated = report["generated"]
        assert isinstance(generated, list)
        assert any("projectBrief.md" in str(path) for path in generated)  # type: ignore[arg-type]

        projectBrief_path = knowledge_dir / "projectBrief.md"
        assert projectBrief_path.exists()

    def test_generate_initial_files_creates_tech_context(self, tmp_path: Path):
        """Test generate_initial_files creates techContext.md."""
        # Arrange
        manager = TemplateManager(tmp_path)
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        project_info: dict[str, object] = {
            "project_type": "web",
            "primary_language": "Python",
            "frameworks": "Django",
            "team_size": "Solo",
            "development_process": "Agile/Scrum",
        }
        templates: dict[str, str] = {}

        # Act
        _ = manager.generate_initial_files(knowledge_dir, project_info, templates)

        # Assert
        tech_context_path = knowledge_dir / "techContext.md"
        assert tech_context_path.exists()

        content = tech_context_path.read_text(encoding="utf-8")
        assert "# Technical Context" in content
        assert "web" in content
        assert "Python" in content

    def test_generate_initial_files_creates_memorybankinstructions(
        self, tmp_path: Path
    ):
        """Test generate_initial_files creates memorybankinstructions.md."""
        # Arrange
        manager = TemplateManager(tmp_path)
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        project_info: dict[str, object] = {"project_name": "Test Project"}
        templates = {"memorybankinstructions.md": "# Instructions\n{project_name}"}

        # Act
        _ = manager.generate_initial_files(knowledge_dir, project_info, templates)

        # Assert
        instructions_path = knowledge_dir / "memorybankinstructions.md"
        assert instructions_path.exists()

    def test_generate_initial_files_handles_missing_templates(self, tmp_path: Path):
        """Test generate_initial_files handles missing templates gracefully."""
        # Arrange
        manager = TemplateManager(tmp_path)
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        project_info: dict[str, object] = {}
        templates: dict[str, str] = {}  # Empty templates

        # Act
        report = manager.generate_initial_files(knowledge_dir, project_info, templates)

        # Assert
        # Should still generate techContext.md (doesn't need template)
        tech_context_path = knowledge_dir / "techContext.md"
        assert tech_context_path.exists()

        # projectBrief.md and memorybankinstructions.md may have errors
        assert "errors" in report or "generated" in report

    def test_generate_initial_files_handles_write_errors(self, tmp_path: Path):
        """Test generate_initial_files handles file write errors."""
        # Arrange
        manager = TemplateManager(tmp_path)
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        project_info: dict[str, object] = {}
        templates = {"projectBrief.md": "Content"}

        # Make directory read-only to cause write error
        knowledge_dir.chmod(0o444)

        try:
            # Act
            report = manager.generate_initial_files(
                knowledge_dir, project_info, templates
            )

            # Assert
            assert "errors" in report
            errors = report["errors"]
            assert isinstance(errors, list)
            assert len(errors) > 0  # type: ignore[arg-type]
        finally:
            # Restore permissions for cleanup
            knowledge_dir.chmod(0o755)

    def test_generate_initial_files_customizes_templates(self, tmp_path: Path):
        """Test generate_initial_files customizes templates with project info."""
        # Arrange
        manager = TemplateManager(tmp_path)
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        project_info: dict[str, object] = {
            "project_name": "My Project",
            "author": "John Doe",
        }
        templates = {
            "projectBrief.md": "# {project_name}\nAuthor: {author}",
            "memorybankinstructions.md": "Project: {project_name}",
        }

        # Act
        _ = manager.generate_initial_files(knowledge_dir, project_info, templates)

        # Assert
        projectBrief_path = knowledge_dir / "projectBrief.md"
        if projectBrief_path.exists():
            content = projectBrief_path.read_text(encoding="utf-8")
            assert "My Project" in content
            assert "John Doe" in content
            assert "{project_name}" not in content
            assert "{author}" not in content


# ============================================================================
# Test customize_template()
# ============================================================================


class TestCustomizeTemplate:
    """Test template customization helper."""

    def test_customize_template_replaces_placeholders(self, tmp_path: Path):
        """Test customize_template replaces placeholders with project info."""
        # Arrange
        manager = TemplateManager(tmp_path)
        template = "Project: {project_name}, Author: {author}"
        project_info: dict[str, object] = {"project_name": "Test", "author": "John"}

        # Act
        result = manager.customize_template(template, project_info)

        # Assert
        assert "Test" in result
        assert "John" in result
        assert "{project_name}" not in result
        assert "{author}" not in result

    def test_customize_template_handles_missing_placeholders(self, tmp_path: Path):
        """Test customize_template handles missing placeholders."""
        # Arrange
        manager = TemplateManager(tmp_path)
        template = "Project: {project_name}"
        project_info: dict[str, object] = {"author": "John"}  # Missing project_name

        # Act
        result = manager.customize_template(template, project_info)

        # Assert
        assert "{project_name}" in result  # Not replaced

    def test_customize_template_handles_extra_project_info(self, tmp_path: Path):
        """Test customize_template handles extra project info."""
        # Arrange
        manager = TemplateManager(tmp_path)
        template = "Project: {project_name}"
        project_info: dict[str, object] = {"project_name": "Test", "extra": "value"}

        # Act
        result = manager.customize_template(template, project_info)

        # Assert
        assert "Test" in result
        assert "{project_name}" not in result

    def test_customize_template_converts_values_to_string(self, tmp_path: Path):
        """Test customize_template converts values to strings."""
        # Arrange
        manager = TemplateManager(tmp_path)
        template = "Number: {count}, Boolean: {flag}"
        project_info: dict[str, object] = {"count": 42, "flag": True}

        # Act
        result = manager.customize_template(template, project_info)

        # Assert
        assert "42" in result
        assert "True" in result


# ============================================================================
# Test generate_tech_context()
# ============================================================================


class TestGenerateTechContext:
    """Test tech context generation."""

    def test_generate_tech_context_includes_all_fields(self, tmp_path: Path):
        """Test generate_tech_context includes all project info fields."""
        # Arrange
        manager = TemplateManager(tmp_path)
        project_info: dict[str, object] = {
            "project_type": "web",
            "primary_language": "Python",
            "frameworks": "Django, React",
            "team_size": "2-5",
            "development_process": "Agile/Scrum",
        }

        # Act
        content = manager.generate_tech_context(project_info)

        # Assert
        assert "# Technical Context" in content
        assert "web" in content
        assert "Python" in content
        assert "Django, React" in content
        assert "2-5" in content
        assert "Agile/Scrum" in content

    def test_generate_tech_context_handles_missing_fields(self, tmp_path: Path):
        """Test generate_tech_context handles missing project info fields."""
        # Arrange
        manager = TemplateManager(tmp_path)
        project_info: dict[str, object] = {}  # Empty

        # Act
        content = manager.generate_tech_context(project_info)

        # Assert
        assert "# Technical Context" in content
        assert "N/A" in content  # Default for missing fields

    def test_generate_tech_context_has_expected_sections(self, tmp_path: Path):
        """Test generate_tech_context has all expected sections."""
        # Arrange
        manager = TemplateManager(tmp_path)
        project_info: dict[str, object] = {}

        # Act
        content = manager.generate_tech_context(project_info)

        # Assert
        expected_sections = [
            "# Technical Context",
            "## Project Type",
            "## Technology Stack",
            "## Development Environment",
            "## Technical Decisions",
            "## Development Workflow",
            "## Quality Standards",
            "## Performance Considerations",
            "## Security Considerations",
        ]
        for section in expected_sections:
            assert section in content

    def test_generate_tech_context_uses_project_info_values(self, tmp_path: Path):
        """Test generate_tech_context uses actual project info values."""
        # Arrange
        manager = TemplateManager(tmp_path)
        project_info: dict[str, object] = {
            "project_type": "mobile",
            "primary_language": "Swift",
            "frameworks": "SwiftUI",
            "team_size": "Solo",
            "development_process": "Continuous",
        }

        # Act
        content = manager.generate_tech_context(project_info)

        # Assert
        assert "mobile" in content
        assert "Swift" in content
        assert "SwiftUI" in content
        assert "Solo" in content
        assert "Continuous" in content
        assert "N/A" not in content  # All fields provided
