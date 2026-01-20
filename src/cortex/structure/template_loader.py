#!/usr/bin/env python3
"""
Template loading utilities for MCP Memory Bank (Phase 8).

This module handles template constants and file creation operations.
"""

from pathlib import Path

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


def create_plan_templates(
    plans_dir: Path, plan_templates: dict[str, str]
) -> dict[str, list[str]]:
    """Create plan template files.

    Args:
        plans_dir: Plans directory path
        plan_templates: Dictionary of plan templates

    Returns:
        Report of created templates with keys: created, skipped, errors
    """
    templates_dir = plans_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    created_list: list[str] = []
    skipped_list: list[str] = []
    errors_list: list[str] = []

    for template_name, template_content in plan_templates.items():
        template_path = templates_dir / template_name

        if template_path.exists():
            skipped_list.append(str(template_path))
            continue

        try:
            _ = template_path.write_text(template_content, encoding="utf-8")
            created_list.append(str(template_path))
        except Exception as e:
            errors_list.append(f"Failed to create {template_name}: {e}")

    return {
        "created": created_list,
        "skipped": skipped_list,
        "errors": errors_list,
    }
