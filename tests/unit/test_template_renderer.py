from pathlib import Path

import pytest

from cortex.structure.template_renderer import (
    customize_template,
    generate_initial_files,
    generate_plan,
    generate_rule,
    generate_tech_context,
)


def test_generate_plan_when_unknown_type_raises_value_error() -> None:
    # Arrange
    templates = {"feature.md": "Created {date} - [Feature Name]"}

    # Act / Assert
    with pytest.raises(ValueError, match="Unknown plan type"):
        _ = generate_plan("does-not-exist.md", "My Plan", templates)


def test_generate_plan_substitutes_variables_and_title() -> None:
    # Arrange
    templates = {
        "feature.md": (
            "Created {date}\nName: {plan_name}\n# [Feature Name]\n" "Team: {team}"
        )
    }

    # Act
    content = generate_plan(
        "feature.md",
        "Improve onboarding",
        templates,
        variables={"team": "Core"},
    )

    # Assert
    assert "Improve onboarding" in content
    assert "Team: Core" in content


def test_generate_rule_when_unknown_type_raises_value_error() -> None:
    # Arrange
    templates = {"coding-standards": "# Standards"}

    # Act / Assert
    with pytest.raises(ValueError, match="Unknown rule type"):
        _ = generate_rule("does-not-exist", templates)


def test_generate_rule_formats_when_variables_provided() -> None:
    # Arrange
    templates = {"coding-standards": "Owner: {owner}"}

    # Act
    content = generate_rule(
        "coding-standards", templates, variables={"owner": "Platform"}
    )

    # Assert
    assert content == "Owner: Platform"


def test_customize_template_replaces_only_known_placeholders() -> None:
    # Arrange
    template = "Project: {name}\nLanguage: {lang}\nUnchanged: {missing}"
    project_info = {"name": "Cortex", "lang": "Python"}

    # Act
    result = customize_template(template, project_info)

    # Assert
    assert "Project: Cortex" in result
    assert "Language: Python" in result
    assert "{missing}" in result


def test_generate_tech_context_includes_project_info_defaults() -> None:
    # Arrange
    project_info = {"project_type": "Library", "primary_language": "Python"}

    # Act
    content = generate_tech_context(project_info)

    # Assert
    assert "## Project Type" in content
    assert "Library" in content
    assert "### Primary Language" in content
    assert "Python" in content


def test_generate_initial_files_writes_expected_files(tmp_path: Path) -> None:
    # Arrange
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True)
    project_info = {"name": "Cortex"}
    templates = {
        "projectBrief.md": "# {name}\n",
        "memorybankinstructions.md": "Use {name}\n",
    }

    # Act
    report = generate_initial_files(knowledge_dir, project_info, templates)

    # Assert
    assert report["errors"] == []
    assert (knowledge_dir / "projectBrief.md").exists()
    assert (knowledge_dir / "techContext.md").exists()
    assert (knowledge_dir / "memorybankinstructions.md").exists()


def test_generate_initial_files_when_write_fails_reports_errors(tmp_path: Path) -> None:
    # Arrange
    knowledge_dir = tmp_path / "not-a-dir"
    project_info = {"name": "Cortex"}
    templates = {
        "projectBrief.md": "# {name}\n",
        "memorybankinstructions.md": "Use {name}\n",
    }

    # Act
    report = generate_initial_files(knowledge_dir, project_info, templates)

    # Assert
    assert report["generated"] == []
    assert len(report["errors"]) == 3
