"""Shared schema-aligned content for Memory Bank integration tests.

Provides minimal valid content for projectBrief.md and other schema-validated
files so tests stay aligned with schema_validator required sections.
See src/cortex/validation/schema_validator.py DEFAULT_SCHEMAS.
"""

from __future__ import annotations

# projectBrief.md required sections (schema_validator.DEFAULT_SCHEMAS)
PROJECT_BRIEF_REQUIRED_SECTIONS: tuple[str, ...] = (
    "Project Overview",
    "Goals",
    "Core Requirements",
    "Success Criteria",
)

# Minimal content that satisfies projectBrief.md schema (all four required sections).
# Use in integration tests that write projectBrief.md to avoid schema validation failures.
MINIMAL_VALID_PROJECT_BRIEF_CONTENT: str = (
    "## Project Overview\n\nOverview.\n\n"
    "## Goals\n\n- Goal.\n\n"
    "## Core Requirements\n\n- Requirement.\n\n"
    "## Success Criteria\n\nCriteria.\n"
)
