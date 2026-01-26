from pathlib import Path

from cortex.structure.template_loader import PLAN_TEMPLATES, create_plan_templates


def test_plan_templates_contains_expected_templates() -> None:
    # Arrange / Act
    templates = PLAN_TEMPLATES

    # Assert
    assert "feature.md" in templates
    assert "bugfix.md" in templates
    assert "refactoring.md" in templates
    assert "research.md" in templates
    assert "{date}" in templates["feature.md"]


def test_create_plan_templates_creates_files_and_then_skips_existing(
    tmp_path: Path,
) -> None:
    # Arrange
    plans_dir = tmp_path / "plans"
    plan_templates = {
        "feature.md": "# Feature",
        "bugfix.md": "# Bugfix",
    }

    # Act
    first = create_plan_templates(plans_dir, plan_templates)
    second = create_plan_templates(plans_dir, plan_templates)

    # Assert
    assert len(first["created"]) == 2
    assert first["skipped"] == []
    assert first["errors"] == []

    assert second["created"] == []
    assert len(second["skipped"]) == 2
    assert second["errors"] == []


def test_create_plan_templates_when_write_fails_reports_error(tmp_path: Path) -> None:
    # Arrange
    plans_dir = tmp_path / "plans"
    # Use nested path so write_text fails (parent dir doesn't exist)
    plan_templates = {"nested/template.md": "# Template"}

    # Act
    result = create_plan_templates(plans_dir, plan_templates)

    # Assert
    assert result["created"] == []
    assert result["skipped"] == []
    assert len(result["errors"]) == 1
