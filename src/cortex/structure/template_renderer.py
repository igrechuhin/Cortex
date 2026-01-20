#!/usr/bin/env python3
"""
Template rendering utilities for MCP Memory Bank (Phase 8).

This module handles template rendering, customization, and file generation.
"""

from datetime import datetime
from pathlib import Path


def generate_plan(
    plan_type: str,
    plan_name: str,
    plan_templates: dict[str, str],
    variables: dict[str, str] | None = None,
) -> str:
    """Generate a plan from a template.

    Args:
        plan_type: Type of plan (feature, bugfix, refactoring, research)
        plan_name: Name for the plan
        plan_templates: Dictionary of plan templates
        variables: Additional variables to substitute

    Returns:
        Generated plan content

    Raises:
        ValueError: If plan_type is not in plan_templates
    """
    if plan_type not in plan_templates:
        raise ValueError(f"Unknown plan type: {plan_type}")

    template = plan_templates[plan_type]

    # Default variables
    vars_dict = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "plan_name": plan_name,
    }

    # Merge with provided variables
    if variables:
        vars_dict.update(variables)

    # Substitute variables
    content = template.format(**vars_dict)

    # Replace title placeholder
    content = content.replace("[Feature Name]", plan_name, 1)
    content = content.replace("[Bug Description]", plan_name, 1)
    content = content.replace("[Refactoring Title]", plan_name, 1)
    content = content.replace("[Research Topic]", plan_name, 1)

    return content


def generate_rule(
    rule_type: str,
    rule_templates: dict[str, str],
    variables: dict[str, str] | None = None,
) -> str:
    """Generate a rule from a template.

    Args:
        rule_type: Type of rule (coding-standards, architecture, testing)
        rule_templates: Dictionary of rule templates
        variables: Additional variables to substitute

    Returns:
        Generated rule content

    Raises:
        ValueError: If rule_type is not in rule_templates
    """
    if rule_type not in rule_templates:
        raise ValueError(f"Unknown rule type: {rule_type}")

    template = rule_templates[rule_type]

    if variables:
        template = template.format(**variables)

    return template


def customize_template(template: str, project_info: dict[str, str]) -> str:
    """Customize a template with project information.

    Args:
        template: Template content
        project_info: Project information as string dict

    Returns:
        Customized template
    """
    # Replace placeholders with project info
    content = template
    for key, value in project_info.items():
        placeholder = f"{{{key}}}"
        if placeholder in content:
            content = content.replace(placeholder, value)
    return content


def generate_tech_context(project_info: dict[str, str]) -> str:
    """Generate techContext.md from project information.

    Args:
        project_info: Project information

    Returns:
        Generated content
    """
    return f"""# Technical Context

## Project Type
{project_info.get("project_type", "N/A")}

## Technology Stack

### Primary Language
{project_info.get("primary_language", "N/A")}

### Frameworks & Libraries
{project_info.get("frameworks", "N/A")}

### Architecture Style
[To be defined based on project evolution]

## Development Environment

### Setup Requirements
- [List required tools and versions]
- [Configuration needed]

### Build & Deploy
- Build process: [description]
- Deployment target: [description]

## Technical Decisions

### Why This Stack?
[Rationale for technology choices]

### Trade-offs
[Known limitations and trade-offs]

## Development Workflow

### Team Size
{project_info.get("team_size", "N/A")}

### Process
{project_info.get("development_process", "N/A")}

### Code Review
[Required/Optional and process]

## Quality Standards

### Testing
- Unit tests: [requirement]
- Integration tests: [requirement]
- E2E tests: [requirement]

### Code Quality
- Linting: [tools used]
- Type checking: [enabled/disabled]
- Coverage: [target percentage]

## Performance Considerations
[Key performance requirements and constraints]

## Security Considerations
[Security requirements and practices]
"""


def generate_initial_files(
    knowledge_dir: Path,
    project_info: dict[str, str],
    templates: dict[str, str],
) -> dict[str, list[str]]:
    """Generate initial memory bank files from project information.

    Args:
        knowledge_dir: Knowledge directory path
        project_info: Project information from interview
        templates: Templates dictionary

    Returns:
        Report of generated files with keys: generated, errors
    """
    generated_list: list[str] = []
    errors_list: list[str] = []

    _generate_projectBrief_file(
        knowledge_dir, project_info, templates, generated_list, errors_list
    )
    _generate_tech_context_file(
        knowledge_dir, project_info, generated_list, errors_list
    )
    _generate_instructions_file(
        knowledge_dir, project_info, templates, generated_list, errors_list
    )

    return {"generated": generated_list, "errors": errors_list}


def _generate_projectBrief_file(
    knowledge_dir: Path,
    project_info: dict[str, str],
    templates: dict[str, str],
    generated_list: list[str],
    errors_list: list[str],
) -> None:
    """Generate projectBrief.md file."""
    try:
        content = customize_template(templates.get("projectBrief.md", ""), project_info)
        file_path = knowledge_dir / "projectBrief.md"
        _ = file_path.write_text(content, encoding="utf-8")
        generated_list.append(str(file_path))
    except Exception as e:
        errors_list.append(f"Failed to generate projectBrief.md: {e}")


def _generate_tech_context_file(
    knowledge_dir: Path,
    project_info: dict[str, str],
    generated_list: list[str],
    errors_list: list[str],
) -> None:
    """Generate techContext.md file."""
    try:
        content = generate_tech_context(project_info)
        file_path = knowledge_dir / "techContext.md"
        _ = file_path.write_text(content, encoding="utf-8")
        generated_list.append(str(file_path))
    except Exception as e:
        errors_list.append(f"Failed to generate techContext.md: {e}")


def _generate_instructions_file(
    knowledge_dir: Path,
    project_info: dict[str, str],
    templates: dict[str, str],
    generated_list: list[str],
    errors_list: list[str],
) -> None:
    """Generate memorybankinstructions.md file."""
    try:
        content = customize_template(
            templates.get("memorybankinstructions.md", ""), project_info
        )
        file_path = knowledge_dir / "memorybankinstructions.md"
        _ = file_path.write_text(content, encoding="utf-8")
        generated_list.append(str(file_path))
    except Exception as e:
        errors_list.append(f"Failed to generate memorybankinstructions.md: {e}")
