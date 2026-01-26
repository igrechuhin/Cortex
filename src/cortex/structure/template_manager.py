#!/usr/bin/env python3
"""
Template Manager for MCP Memory Bank (Phase 8).

This module manages templates for plans, rules, and knowledge files.
Provides interactive setup and template generation.
"""

from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict


class TemplateManager:
    """Manages templates for Memory Bank files, plans, and rules."""

    # Plan templates
    PLAN_TEMPLATES: dict[str, str] = {
        "feature.md": """# [Feature Name]

## Status
- Phase: Planning
- Progress: 0%
- Created: {date}
- Last Updated: {date}

## Goal
Clear statement of what this feature achieves

## Context
Why this feature is needed, user needs, business requirements

## Approach
High-level implementation strategy

## Implementation Steps
1. [ ] Step one - Description
2. [ ] Step two - Description
3. [ ] Step three - Description

## Dependencies
- Depends on: [other-plan.md or external dependency]
- Blocks: [future-plan.md]

## Success Criteria
- [ ] Criterion 1 - measurable outcome
- [ ] Criterion 2 - measurable outcome

## Technical Design
### Architecture
- Component changes
- New modules/classes

### Data Model
- Database changes
- API contracts

### UI/UX
- Interface changes
- User flows

## Testing Strategy
- Unit tests: [scope]
- Integration tests: [scope]
- E2E tests: [scope]
- Manual testing: [checklist]

## Risks & Mitigation
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ... | High/Med/Low | High/Med/Low | ... |

## Timeline
- Sprint 1: [scope and deliverables]
- Sprint 2: [scope and deliverables]

## Rollback Plan
How to undo changes if needed

## Notes
- Additional context
- Decisions made
- Open questions
""",
        "bugfix.md": """# [Bug Description]

## Status
- Phase: Investigation
- Progress: 0%
- Created: {date}
- Last Updated: {date}
- Priority: [Critical/High/Medium/Low]

## Problem Description
Clear description of the bug and its symptoms

## Impact
- Affected users: [scope]
- Severity: [Critical/High/Medium/Low]
- Frequency: [Always/Often/Sometimes/Rare]

## Steps to Reproduce
1. Step one
2. Step two
3. Expected vs Actual behavior

## Root Cause Analysis
### Investigation
- What was investigated
- Findings

### Root Cause
- Why the bug occurs
- Code/design issue

## Solution
### Approach
High-level fix strategy

### Implementation
- [ ] Change 1 - Description
- [ ] Change 2 - Description
- [ ] Change 3 - Description

## Testing
- [ ] Verify fix resolves original issue
- [ ] Regression testing
- [ ] Edge cases covered

## Prevention
How to prevent similar bugs in the future

## Notes
- Related issues
- Workarounds
- Additional context
""",
        "refactoring.md": """# [Refactoring Title]

## Status
- Phase: Planning
- Progress: 0%
- Created: {date}
- Last Updated: {date}

## Goal
What we aim to improve through this refactoring

## Current State
Description of current code/architecture issues

### Problems
- Problem 1: Description and impact
- Problem 2: Description and impact

### Metrics
- Current complexity metrics
- Current performance metrics
- Current maintainability issues

## Target State
Description of desired end state

### Improvements
- Improvement 1: Expected benefit
- Improvement 2: Expected benefit

### Metrics Goals
- Target complexity reduction
- Target performance improvement
- Target maintainability improvement

## Approach
### Strategy
- Step-by-step refactoring approach
- Backward compatibility considerations

### Changes Required
1. [ ] Change 1 - Description
2. [ ] Change 2 - Description
3. [ ] Change 3 - Description

## Testing Strategy
- [ ] Existing tests continue to pass
- [ ] New tests for refactored code
- [ ] Performance benchmarks
- [ ] Integration tests

## Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes | High | [mitigation strategy] |
| Performance regression | Medium | [mitigation strategy] |

## Rollback Plan
- How to revert changes
- Monitoring strategy

## Timeline
- Phase 1: [scope]
- Phase 2: [scope]

## Success Criteria
- [ ] All tests pass
- [ ] Performance maintained or improved
- [ ] Code complexity reduced
- [ ] Documentation updated
""",
        "research.md": """# [Research Topic]

## Status
- Phase: Research
- Progress: 0%
- Created: {date}
- Last Updated: {date}

## Goal
What we want to learn or decide

## Context
Why this research is needed, background information

## Questions to Answer
1. Question 1?
2. Question 2?
3. Question 3?

## Approach
### Research Methods
- [ ] Literature review
- [ ] Competitive analysis
- [ ] Prototyping
- [ ] Performance testing
- [ ] User interviews

### Resources
- Documentation
- Tools/frameworks to evaluate
- People to consult

## Findings
### Investigation 1
- What was tested/researched
- Results
- Conclusions

### Investigation 2
- What was tested/researched
- Results
- Conclusions

## Recommendations
### Option 1: [Name]
**Pros:**
- Pro 1
- Pro 2

**Cons:**
- Con 1
- Con 2

**Effort:** [High/Medium/Low]

### Option 2: [Name]
**Pros:**
- Pro 1
- Pro 2

**Cons:**
- Con 1
- Con 2

**Effort:** [High/Medium/Low]

### Decision
Final recommendation with rationale

## Next Steps
- [ ] Action item 1
- [ ] Action item 2

## References
- Link 1: Description
- Link 2: Description
""",
    }

    # Rule templates
    RULE_TEMPLATES: dict[str, str] = {
        "coding-standards.md": """# Coding Standards

## Context
This rule applies to: {language}

## Standards

### Naming Conventions
- Classes: PascalCase
- Functions: snake_case
- Variables: snake_case
- Constants: UPPER_SNAKE_CASE

### Code Style
- Indentation: [spaces/tabs] x [number]
- Line length: [max characters]
- Documentation: [required for all public methods]

### Best Practices
1. Practice 1: Description
2. Practice 2: Description

## Examples

### ✅ Good
```python
def calculate_total_price(items: list[Item]) -> Decimal:
    \"\"\"Calculate total price including tax.

    Args:
        items: List of items to price

    Returns:
        Total price with tax
    \"\"\"
    return sum(item.price for item in items) * Decimal('1.1')
```

### ❌ Bad
```python
def calc(i):
    return sum([x.price for x in i]) * 1.1
```

## Rationale
Why these standards exist and their benefits

## Exceptions
When it's acceptable to deviate from these standards

## Metadata
- Category: coding-style
- Languages: [python, javascript]
- Priority: required
""",
        "architecture.md": """# Architecture Guidelines

## Context
Architectural patterns and design principles for this project

## Patterns

### Layered Architecture
- Presentation Layer: [description]
- Business Logic Layer: [description]
- Data Access Layer: [description]

### Design Patterns
1. Pattern 1: When to use
2. Pattern 2: When to use

## Principles

### SOLID Principles
- Single Responsibility
- Open/Closed
- Liskov Substitution
- Interface Segregation
- Dependency Inversion

### Domain-Driven Design
- Bounded contexts
- Aggregates
- Entities vs Value Objects

## Examples

### ✅ Good Architecture
```python
class UserService:
    def __init__(self, repository: UserRepository, validator: UserValidator):
        self.repository = repository
        self.validator = validator

    async def create_user(self, data: UserCreate) -> User:
        self.validator.validate(data)
        return await self.repository.save(data)
```

### ❌ Poor Architecture
```python
def create_user(data):
    # Mix of validation, business logic, and data access
    if not data.email: raise Error()
    db.execute("INSERT INTO users ...")
    send_email(data.email)
```

## Rationale
Why these architectural decisions matter

## Metadata
- Category: architecture
- Priority: required
""",
        "testing.md": """# Testing Standards

## Context
Testing requirements and best practices

## Requirements

### Test Coverage
- Minimum coverage: [percentage]
- Critical paths: 100% coverage
- Edge cases: Must be tested

### Test Types
1. **Unit Tests**: [requirements]
2. **Integration Tests**: [requirements]
3. **E2E Tests**: [requirements]

## Standards

### Test Structure
```python
def test_feature_scenario():
    # Arrange
    setup_test_data()

    # Act
    result = perform_action()

    # Assert
    assert result == expected
```

### Naming Conventions
- Test files: `test_*.py`
- Test functions: `test_[feature]_[scenario]`
- Descriptive names

## Examples

### ✅ Good Test
```python
async def test_create_user_with_valid_data_succeeds():
    # Arrange
    user_data = UserCreate(email="test@example.com", name="Test User")

    # Act
    result = await user_service.create_user(user_data)

    # Assert
    assert result.email == user_data.email
    assert result.id is not None
```

### ❌ Bad Test
```python
def test1():
    u = create("test")
    assert u
```

## Metadata
- Category: testing
- Priority: required
""",
    }

    def __init__(self, project_root: Path):
        """Initialize the template manager.

        Args:
            project_root: Root directory of the project
        """
        self.project_root: Path = project_root

    def generate_plan(
        self, plan_type: str, plan_name: str, variables: dict[str, str] | None = None
    ) -> str:
        """Generate a plan from a template.

        Args:
            plan_type: Type of plan (feature, bugfix, refactoring, research)
            plan_name: Name for the plan
            variables: Additional variables to substitute

        Returns:
            Generated plan content
        """
        if plan_type not in self.PLAN_TEMPLATES:
            raise ValueError(f"Unknown plan type: {plan_type}")

        template = self.PLAN_TEMPLATES[plan_type]

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
        self, rule_type: str, variables: dict[str, str] | None = None
    ) -> str:
        """Generate a rule from a template.

        Args:
            rule_type: Type of rule (coding-standards, architecture, testing)
            variables: Additional variables to substitute

        Returns:
            Generated rule content
        """
        if rule_type not in self.RULE_TEMPLATES:
            raise ValueError(f"Unknown rule type: {rule_type}")

        template = self.RULE_TEMPLATES[rule_type]

        if variables:
            template = template.format(**variables)

        return template

    def create_plan_templates(self, plans_dir: Path) -> ModelDict:
        """Create plan template files.

        Args:
            plans_dir: Plans directory path

        Returns:
            Report of created templates
        """
        templates_dir = plans_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        created_list: list[str] = []
        skipped_list: list[str] = []
        errors_list: list[str] = []
        created_json = cast(list[JsonValue], created_list)
        skipped_json = cast(list[JsonValue], skipped_list)
        errors_json = cast(list[JsonValue], errors_list)
        report: ModelDict = {
            "created": created_json,
            "skipped": skipped_json,
            "errors": errors_json,
        }

        for template_name, template_content in self.PLAN_TEMPLATES.items():
            template_path = templates_dir / template_name

            if template_path.exists():
                skipped_list.append(str(template_path))
                continue

            try:
                _ = template_path.write_text(template_content, encoding="utf-8")
                created_list.append(str(template_path))
            except Exception as e:
                errors_list.append(f"Failed to create {template_name}: {e}")

        return report

    def interactive_project_setup(self) -> ModelDict:
        """Interactive interview for project setup.

        Returns:
            Collected project information
        """
        questions: list[ModelDict] = []
        questions.extend(self._build_basic_info_questions())
        questions.extend(self._build_technical_questions())
        questions.extend(self._build_team_process_questions())
        questions.extend(self._build_configuration_questions())

        questions_json: list[JsonValue] = [cast(JsonValue, q) for q in questions]
        return {"questions": questions_json}

    def _build_basic_info_questions(self) -> list[ModelDict]:
        """Build basic project information questions.

        Returns:
            List of question dictionaries
        """
        return [
            {
                "id": "project_name",
                "question": "What is the project name?",
                "type": "text",
            },
            {
                "id": "project_description",
                "question": "What is this project about? (Brief description)",
                "type": "text",
            },
        ]

    def _build_technical_questions(self) -> list[ModelDict]:
        """Build technical questions.

        Returns:
            List of question dictionaries
        """
        questions: list[ModelDict] = []
        questions.append(self._build_project_type_question())
        questions.append(self._build_language_question())
        questions.append(self._build_frameworks_question())
        return questions

    def _build_project_type_question(self) -> ModelDict:
        """Build project type question.

        Returns:
            Question dictionary
        """
        return {
            "id": "project_type",
            "question": "What type of project is this?",
            "type": "choice",
            "options": [
                "web",
                "mobile",
                "backend",
                "library",
                "cli",
                "desktop",
            ],
        }

    def _build_language_question(self) -> ModelDict:
        """Build primary language question.

        Returns:
            Question dictionary
        """
        return {
            "id": "primary_language",
            "question": "Primary programming language?",
            "type": "choice",
            "options": [
                "Python",
                "JavaScript",
                "TypeScript",
                "Swift",
                "Rust",
                "Go",
                "Java",
                "C#",
                "Other",
            ],
        }

    def _build_frameworks_question(self) -> ModelDict:
        """Build frameworks question.

        Returns:
            Question dictionary
        """
        return {
            "id": "frameworks",
            "question": "Main frameworks/libraries used?",
            "type": "text",
        }

    def _build_team_process_questions(self) -> list[ModelDict]:
        """Build team and process questions.

        Returns:
            List of question dictionaries
        """
        return [
            {
                "id": "team_size",
                "question": "Team size?",
                "type": "choice",
                "options": ["Solo", "2-5", "6-20", "21+"],
            },
            {
                "id": "development_process",
                "question": "Development process?",
                "type": "choice",
                "options": [
                    "Agile/Scrum",
                    "Kanban",
                    "Waterfall",
                    "Continuous",
                    "Informal",
                ],
            },
        ]

    def _build_configuration_questions(self) -> list[ModelDict]:
        """Build configuration questions.

        Returns:
            List of question dictionaries
        """
        return [
            {
                "id": "use_shared_rules",
                "question": "Use shared rules repository?",
                "type": "boolean",
            },
        ]

    def generate_initial_files(
        self,
        knowledge_dir: Path,
        project_info: ModelDict,
        templates: dict[str, str],
    ) -> ModelDict:
        """Generate initial memory bank files from project information.

        Args:
            knowledge_dir: Knowledge directory path
            project_info: Project information from interview
            templates: Templates dictionary

        Returns:
            Report of generated files
        """
        generated_list: list[str] = []
        errors_list: list[str] = []
        generated_json = cast(list[JsonValue], generated_list)
        errors_json = cast(list[JsonValue], errors_list)
        report: ModelDict = {"generated": generated_json, "errors": errors_json}

        self._generate_projectBrief_file(
            knowledge_dir, project_info, templates, generated_list, errors_list
        )
        self._generate_tech_context_file(
            knowledge_dir, project_info, generated_list, errors_list
        )
        self._generate_instructions_file(
            knowledge_dir, project_info, templates, generated_list, errors_list
        )

        return report

    def _generate_projectBrief_file(
        self,
        knowledge_dir: Path,
        project_info: ModelDict,
        templates: dict[str, str],
        generated_list: list[str],
        errors_list: list[str],
    ) -> None:
        """Generate projectBrief.md file."""
        try:
            content = self.customize_template(
                templates.get("projectBrief.md", ""), project_info
            )
            file_path = knowledge_dir / "projectBrief.md"
            _ = file_path.write_text(content, encoding="utf-8")
            generated_list.append(str(file_path))
        except Exception as e:
            errors_list.append(f"Failed to generate projectBrief.md: {e}")

    def _generate_tech_context_file(
        self,
        knowledge_dir: Path,
        project_info: ModelDict,
        generated_list: list[str],
        errors_list: list[str],
    ) -> None:
        """Generate techContext.md file."""
        try:
            content = self.generate_tech_context(project_info)
            file_path = knowledge_dir / "techContext.md"
            _ = file_path.write_text(content, encoding="utf-8")
            generated_list.append(str(file_path))
        except Exception as e:
            errors_list.append(f"Failed to generate techContext.md: {e}")

    def _generate_instructions_file(
        self,
        knowledge_dir: Path,
        project_info: ModelDict,
        templates: dict[str, str],
        generated_list: list[str],
        errors_list: list[str],
    ) -> None:
        """Generate memorybankinstructions.md file."""
        try:
            content = self.customize_template(
                templates.get("memorybankinstructions.md", ""), project_info
            )
            file_path = knowledge_dir / "memorybankinstructions.md"
            _ = file_path.write_text(content, encoding="utf-8")
            generated_list.append(str(file_path))
        except Exception as e:
            errors_list.append(f"Failed to generate memorybankinstructions.md: {e}")

    def customize_template(self, template: str, project_info: ModelDict) -> str:
        """Customize a template with project information.

        Args:
            template: Template content
            project_info: Project information

        Returns:
            Customized template
        """
        # Replace placeholders with project info
        content = template
        for key, value in project_info.items():
            placeholder = f"{{{key}}}"
            if placeholder in content:
                content = content.replace(placeholder, str(value))
        return content

    def generate_tech_context(self, project_info: ModelDict) -> str:
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
