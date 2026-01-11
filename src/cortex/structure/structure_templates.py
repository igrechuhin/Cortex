#!/usr/bin/env python3
"""README templates for Memory Bank structure directories."""


def generate_plans_readme() -> str:
    """Generate README content for plans directory."""
    return """# Plans Directory

This directory contains all project plans organized by status:

## Structure

- `active/` - Plans currently being worked on
- `completed/` - Finished plans for reference
- `archived/` - Old or deprecated plans
- `templates/` - Plan templates for new plans

## Plan Lifecycle

1. Create new plan in `active/` using a template
2. Update plan as work progresses
3. Move to `completed/` when finished
4. Archive old plans to keep active directory clean

## Templates Available

- `feature.md` - New feature development
- `bugfix.md` - Bug fix plans
- `refactoring.md` - Code refactoring plans
- `research.md` - Research and investigation

## Best Practices

- Keep plans up to date with current progress
- Use clear, descriptive filenames
- Include success criteria and testing strategy
- Link related plans and dependencies
"""


def generate_memory_bank_readme() -> str:
    """Generate README content for memory-bank directory."""
    return """# Memory Bank Directory

This directory contains the Memory Bank knowledge base files.

## Standard Files

- `projectBrief.md` - Project overview and goals
- `productContext.md` - Product context and user needs
- `activeContext.md` - Current active context
- `systemPatterns.md` - System architecture patterns
- `techContext.md` - Technical stack and decisions
- `progress.md` - Project progress tracking
- `roadmap.md` - Development roadmap and milestones

## Organization

- Keep files focused and well-structured
- Use links and transclusions to avoid duplication
- Update regularly to reflect current state
- Follow the Memory Bank file template structure

## Links and Transclusions

Use markdown links to reference other files:
- `[[filename.md#section]]` - Link to specific section
- `{{include: filename.md#section}}` - Include content from another file
"""


def generate_rules_readme() -> str:
    """Generate README content for rules directory."""
    return """# Rules Directory

This directory contains coding standards and rules.

## Structure

- `local/` - Project-specific rules
- `shared/` - Shared rules (git submodule, if configured)

## Local Rules

Project-specific coding standards, architecture decisions, and practices.

- `main.cursorrules` - Main rules file (symlinked to .cursorrules)
- `coding-standards.md` - Coding style guide
- `architecture.md` - Architecture guidelines
- `testing.md` - Testing standards

## Shared Rules

When configured as a git submodule, the `shared/` directory contains
rules shared across multiple projects.

To setup shared rules:
1. Configure shared_repo_url in structure.json
2. Run setup_shared_rules() MCP tool
3. Sync regularly with sync_shared_rules()

## Rule Format

Rules should follow this structure:
- Context (when it applies)
- Standards (specific guidelines)
- Examples (good and bad)
- Rationale (why the rule exists)
- Exceptions (when to deviate)
"""
