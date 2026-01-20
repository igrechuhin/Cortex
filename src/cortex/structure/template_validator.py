#!/usr/bin/env python3
"""
Template validation utilities for MCP Memory Bank (Phase 8).

This module handles template validation logic.
"""


def validate_template_content(template: str) -> bool:
    """Validate template content.

    Args:
        template: Template content to validate

    Returns:
        True if template is valid, False otherwise
    """
    if not template:
        return False

    # Basic validation: template should not be empty
    return bool(template.strip())


def validate_template_variables(
    template: str, provided_variables: dict[str, str]
) -> tuple[bool, list[str]]:
    """Validate that all required template variables are provided.

    Args:
        template: Template content
        provided_variables: Variables provided for substitution

    Returns:
        Tuple of (is_valid, missing_variables)
    """
    # Extract placeholders from template
    import re

    placeholders = re.findall(r"\{(\w+)\}", template)
    required_vars = set(placeholders)

    # Check for missing variables
    provided_vars = set(provided_variables.keys())
    missing_vars = list(required_vars - provided_vars)

    return len(missing_vars) == 0, missing_vars
