#!/usr/bin/env python3
"""
Template Manager for MCP Memory Bank (Phase 8).

Manages templates for plans, rules, and knowledge files.
Delegates to template_loader, template_renderer, template_questions.
"""

from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict

from .template_loader import PLAN_TEMPLATES, RULE_TEMPLATES, create_plan_templates
from .template_questions import build_interactive_setup_questions
from .template_renderer import (
    customize_template as renderer_customize_template,
)
from .template_renderer import (
    generate_initial_files as renderer_generate_initial_files,
)
from .template_renderer import (
    generate_plan as renderer_generate_plan,
)
from .template_renderer import (
    generate_rule as renderer_generate_rule,
)
from .template_renderer import (
    generate_tech_context as renderer_generate_tech_context,
)


class TemplateManager:
    """Manages templates for Memory Bank files, plans, and rules."""

    PLAN_TEMPLATES: dict[str, str] = PLAN_TEMPLATES
    RULE_TEMPLATES: dict[str, str] = RULE_TEMPLATES

    def __init__(self, project_root: Path):
        """Initialize the template manager.

        Args:
            project_root: Root directory of the project
        """
        self.project_root: Path = project_root

    def generate_plan(
        self, plan_type: str, plan_name: str, variables: dict[str, str] | None = None
    ) -> str:
        """Generate a plan from a template."""
        return renderer_generate_plan(
            plan_type, plan_name, self.PLAN_TEMPLATES, variables
        )

    def generate_rule(
        self, rule_type: str, variables: dict[str, str] | None = None
    ) -> str:
        """Generate a rule from a template."""
        return renderer_generate_rule(rule_type, self.RULE_TEMPLATES, variables)

    def create_plan_templates(self, plans_dir: Path) -> ModelDict:
        """Create plan template files."""
        result = create_plan_templates(plans_dir, self.PLAN_TEMPLATES)
        return cast(
            ModelDict,
            {
                "created": cast(list[JsonValue], result["created"]),
                "skipped": cast(list[JsonValue], result["skipped"]),
                "errors": cast(list[JsonValue], result["errors"]),
            },
        )

    def interactive_project_setup(self) -> ModelDict:
        """Interactive interview for project setup."""
        questions = build_interactive_setup_questions()
        questions_json: list[JsonValue] = [cast(JsonValue, q) for q in questions]
        return {"questions": questions_json}

    def generate_initial_files(
        self,
        knowledge_dir: Path,
        project_info: ModelDict,
        templates: dict[str, str],
    ) -> ModelDict:
        """Generate initial memory bank files from project information."""
        project_info_str = {k: str(v) for k, v in project_info.items()}
        result = renderer_generate_initial_files(
            knowledge_dir, project_info_str, templates
        )
        return cast(
            ModelDict,
            {
                "generated": cast(list[JsonValue], result["generated"]),
                "errors": cast(list[JsonValue], result["errors"]),
            },
        )

    def customize_template(self, template: str, project_info: ModelDict) -> str:
        """Customize a template with project information."""
        project_info_str = {k: str(v) for k, v in project_info.items()}
        return renderer_customize_template(template, project_info_str)

    def generate_tech_context(self, project_info: ModelDict) -> str:
        """Generate techContext.md from project information."""
        project_info_str = {k: str(v) for k, v in project_info.items()}
        return renderer_generate_tech_context(project_info_str)
