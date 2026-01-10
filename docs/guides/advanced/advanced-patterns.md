# Advanced Memory Bank Patterns

This guide covers advanced patterns and configurations for using Cortex in complex, enterprise-scale environments.

## Table of Contents

1. [Multi-Repository Setups](#multi-repository-setups)
2. [Enterprise-Scale Configurations](#enterprise-scale-configurations)
3. [CI/CD Pipeline Integration](#cicd-pipeline-integration)
4. [Large Team Collaboration](#large-team-collaboration)
5. [Custom Rule Creation](#custom-rule-creation)
6. [Advanced Transclusion Strategies](#advanced-transclusion-strategies)
7. [Cross-Project Memory Banks](#cross-project-memory-banks)
8. [Memory Bank as Code](#memory-bank-as-code)
9. [Progressive Enhancement Patterns](#progressive-enhancement-patterns)
10. [Advanced Validation Patterns](#advanced-validation-patterns)

---

## Multi-Repository Setups

### Monorepo Configuration

For monorepos with multiple projects, use a hierarchical Memory Bank structure:

```
.cursor/memory-bank/
├── projectBrief.md           # Root-level project overview
├── productContext.md          # Overall product context
├── systemPatterns.md          # Shared architectural patterns
├── techContext.md             # Common tech stack
├── packages/
│   ├── frontend/
│   │   ├── activeContext.md
│   │   ├── progress.md
│   │   └── roadmap.md
│   ├── backend/
│   │   ├── activeContext.md
│   │   ├── progress.md
│   │   └── roadmap.md
│   └── shared/
│       ├── activeContext.md
│       └── progress.md
└── infrastructure/
    ├── activeContext.md
    └── techContext.md
```

**Configuration:**

```json
{
  "memory_bank": {
    "root": ".cursor/memory-bank",
    "structure_type": "hierarchical",
    "package_contexts": {
      "frontend": ".cursor/memory-bank/packages/frontend",
      "backend": ".cursor/memory-bank/packages/backend",
      "shared": ".cursor/memory-bank/packages/shared",
      "infrastructure": ".cursor/memory-bank/infrastructure"
    }
  },
  "transclusion": {
    "search_paths": [
      ".cursor/memory-bank",
      ".cursor/memory-bank/packages/*/",
      ".cursor/memory-bank/infrastructure"
    ]
  }
}
```

**Transclusion Pattern:**

```markdown
<!-- packages/frontend/activeContext.md -->
# Frontend Active Context

## Shared Context

{{include:../../systemPatterns.md#Architecture}}
{{include:../../techContext.md#Frontend Stack}}

## Package-Specific Context

Current Sprint: Phase 3 - Component Library
...
```

### Multi-Repo Coordination

For microservices or multi-repo projects, use shared rules and cross-repository references:

**Central Rules Repository:**

```bash
# Setup central rules repository
git clone https://github.com/your-org/memory-bank-rules.git .cursor/rules-shared

# In each service repository
cd service-a
cortex initialize_shared_rules --repo=https://github.com/your-org/memory-bank-rules.git
```

**Service A Memory Bank:**

```markdown
<!-- .cursor/memory-bank/systemPatterns.md -->
# Service A System Patterns

## Common Patterns

{{include:../.cursor/rules-shared/patterns/microservices.md}}
{{include:../.cursor/rules-shared/patterns/api-design.md}}

## Service-Specific Patterns

### Event-Driven Architecture

This service implements event sourcing with CQRS...
```

**Service B Memory Bank:**

```markdown
<!-- .cursor/memory-bank/systemPatterns.md -->
# Service B System Patterns

## Common Patterns

{{include:../.cursor/rules-shared/patterns/microservices.md}}
{{include:../.cursor/rules-shared/patterns/api-design.md}}

## Service-Specific Patterns

### Data Aggregation Pipeline

This service aggregates data from multiple sources...
```

**Cross-Repository Configuration (.cursor/memory-bank-config.json):**

```json
{
  "shared_rules": {
    "enabled": true,
    "repository": "https://github.com/your-org/memory-bank-rules.git",
    "branch": "main",
    "auto_sync": true,
    "sync_interval": "1h"
  },
  "cross_repo_references": {
    "service-a": "https://github.com/your-org/service-a.git",
    "service-b": "https://github.com/your-org/service-b.git",
    "shared-lib": "https://github.com/your-org/shared-lib.git"
  }
}
```

---

## Enterprise-Scale Configurations

### Large Codebase Optimization

For codebases exceeding 100K LOC, optimize Memory Bank for performance:

```json
{
  "token_budget": {
    "max_total_tokens": 500000,
    "max_file_tokens": 50000,
    "warning_threshold": 0.85,
    "progressive_loading": {
      "enabled": true,
      "batch_size": 5,
      "priority_files": [
        "projectBrief.md",
        "systemPatterns.md",
        "activeContext.md"
      ]
    }
  },
  "caching": {
    "enabled": true,
    "ttl": 3600,
    "max_size": "1GB",
    "strategy": "lru",
    "cache_transclusions": true,
    "cache_validation": true
  },
  "file_watching": {
    "enabled": true,
    "debounce_ms": 500,
    "exclude_patterns": [
      "node_modules/**",
      ".git/**",
      "dist/**",
      "build/**"
    ]
  }
}
```

### Distributed Team Configuration

For teams across multiple time zones and locations:

```json
{
  "collaboration": {
    "lock_timeout": 300,
    "conflict_resolution": "last_write_wins",
    "enable_change_notifications": true,
    "merge_strategy": "three_way"
  },
  "versioning": {
    "snapshot_frequency": "on_save",
    "max_snapshots": 100,
    "enable_rollback": true,
    "backup_to_git": true
  },
  "validation": {
    "pre_commit_hook": true,
    "block_on_validation_error": false,
    "auto_fix": true,
    "notification_level": "warning"
  }
}
```

### Multi-Tenant Memory Banks

For SaaS platforms with per-tenant customization:

```
.cursor/memory-bank/
├── core/                      # Shared across all tenants
│   ├── projectBrief.md
│   ├── systemPatterns.md
│   └── techContext.md
├── tenants/
│   ├── tenant-a/
│   │   ├── productContext.md
│   │   ├── activeContext.md
│   │   └── customizations.md
│   ├── tenant-b/
│   │   ├── productContext.md
│   │   ├── activeContext.md
│   │   └── customizations.md
│   └── template/              # Template for new tenants
│       ├── productContext.md
│       └── activeContext.md
└── shared/
    └── patterns/
        ├── data-isolation.md
        └── security.md
```

**Tenant-Specific Configuration:**

```json
{
  "multi_tenant": {
    "enabled": true,
    "tenant_root": ".cursor/memory-bank/tenants",
    "shared_root": ".cursor/memory-bank/core",
    "tenant_isolation": "strict",
    "tenant_templates": ".cursor/memory-bank/tenants/template"
  },
  "transclusion": {
    "search_paths": [
      ".cursor/memory-bank/core",
      ".cursor/memory-bank/tenants/${TENANT_ID}",
      ".cursor/memory-bank/shared"
    ],
    "tenant_overrides": true
  }
}
```

---

## CI/CD Pipeline Integration

### GitHub Actions Integration

**Validate Memory Bank on Pull Requests:**

```yaml
# .github/workflows/memory-bank-validation.yml
name: Memory Bank Validation

on:
  pull_request:
    paths:
      - '.cursor/memory-bank/**'
      - 'src/**'
      - 'docs/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install Cortex
        run: |
          pip install git+https://github.com/igrechuhin/cortex.git

      - name: Validate Memory Bank
        run: |
          cortex validate_memory_bank --strict

      - name: Check Quality Metrics
        run: |
          cortex calculate_quality_metrics --min-score=8.0

      - name: Detect Duplications
        run: |
          cortex detect_duplications --threshold=0.90

      - name: Validate Links
        run: |
          cortex validate_links --break-on-error

      - name: Generate Validation Report
        if: always()
        run: |
          cortex get_validation_report --format=markdown > validation-report.md

      - name: Upload Report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: validation-report
          path: validation-report.md

      - name: Comment on PR
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('validation-report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Memory Bank Validation Failed\n\n${report}`
            });
```

**Auto-Update Memory Bank on Merge:**

```yaml
# .github/workflows/memory-bank-update.yml
name: Auto-Update Memory Bank

on:
  push:
    branches:
      - main
    paths:
      - 'src/**'
      - 'docs/**'

jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v3
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install Cortex
        run: |
          pip install git+https://github.com/igrechukin/cortex.git

      - name: Analyze Changes
        id: analyze
        run: |
          CHANGES=$(git diff HEAD~1 --name-only)
          echo "changes=$CHANGES" >> $GITHUB_OUTPUT

      - name: Update Progress
        run: |
          cortex analyze_structure --output=.cursor/memory-bank/temp-insights.json
          python scripts/update-progress.py

      - name: Commit Updates
        run: |
          git config user.name "Memory Bank Bot"
          git config user.email "bot@memory-bank.dev"
          git add .cursor/memory-bank/progress.md
          git commit -m "chore: auto-update Memory Bank progress [skip ci]" || echo "No changes"
          git push
```

### GitLab CI Integration

```yaml
# .gitlab-ci.yml
stages:
  - validate
  - analyze
  - report

memory-bank-validate:
  stage: validate
  image: python:3.13
  script:
    - pip install git+https://github.com/igrechukin/cortex.git
    - cortex validate_memory_bank --strict
    - cortex calculate_quality_metrics --min-score=8.0
  only:
    - merge_requests
  artifacts:
    reports:
      junit: validation-report.xml

memory-bank-analyze:
  stage: analyze
  image: python:3.13
  script:
    - pip install git+https://github.com/igrechukin/cortex.git
    - cortex analyze_patterns --output=patterns.json
    - cortex get_insights --output=insights.json
  artifacts:
    paths:
      - patterns.json
      - insights.json
    expire_in: 1 week

memory-bank-report:
  stage: report
  image: python:3.13
  script:
    - pip install git+https://github.com/igrechukin/cortex.git
    - cortex get_validation_report --format=html > report.html
  artifacts:
    paths:
      - report.html
  only:
    - main
```

### Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: memory-bank-validate
        name: Validate Memory Bank
        entry: cortex validate_memory_bank
        language: system
        files: ^\.cursor/memory-bank/.*\.md$
        pass_filenames: false

      - id: memory-bank-links
        name: Validate Memory Bank Links
        entry: cortex validate_links
        language: system
        files: ^\.cursor/memory-bank/.*\.md$
        pass_filenames: false

      - id: memory-bank-quality
        name: Check Memory Bank Quality
        entry: bash -c 'cortex calculate_quality_metrics --min-score=7.0'
        language: system
        files: ^\.cursor/memory-bank/.*\.md$
        pass_filenames: false
```

---

## Large Team Collaboration

### Role-Based Memory Bank Structure

For teams with specialized roles (frontend, backend, DevOps, QA):

```
.cursor/memory-bank/
├── projectBrief.md           # All roles
├── productContext.md         # All roles
├── systemPatterns.md         # All roles
├── roles/
│   ├── frontend/
│   │   ├── activeContext.md
│   │   ├── techContext.md
│   │   ├── progress.md
│   │   └── patterns/
│   │       ├── components.md
│   │       └── state-management.md
│   ├── backend/
│   │   ├── activeContext.md
│   │   ├── techContext.md
│   │   ├── progress.md
│   │   └── patterns/
│   │       ├── api-design.md
│   │       └── database.md
│   ├── devops/
│   │   ├── activeContext.md
│   │   ├── techContext.md
│   │   └── infrastructure.md
│   └── qa/
│       ├── activeContext.md
│       ├── test-strategy.md
│       └── coverage.md
└── integration/
    └── cross-team.md
```

**Role Configuration:**

```json
{
  "roles": {
    "frontend": {
      "files": ["roles/frontend/**"],
      "transclusion_access": ["systemPatterns.md", "productContext.md"],
      "write_permissions": ["roles/frontend/**"],
      "validation_rules": "frontend-specific"
    },
    "backend": {
      "files": ["roles/backend/**"],
      "transclusion_access": ["systemPatterns.md", "productContext.md"],
      "write_permissions": ["roles/backend/**"],
      "validation_rules": "backend-specific"
    },
    "devops": {
      "files": ["roles/devops/**"],
      "transclusion_access": ["systemPatterns.md", "roles/*/techContext.md"],
      "write_permissions": ["roles/devops/**", "systemPatterns.md#Infrastructure"],
      "validation_rules": "devops-specific"
    }
  }
}
```

### Feature Branch Memory Banks

For long-running feature branches:

```bash
# Create feature branch with Memory Bank snapshot
git checkout -b feature/new-payment-system
cortex create_snapshot --name="pre-feature-payment"

# Create feature-specific context
cat > .cursor/memory-bank/features/payment-system.md <<EOF
# Payment System Feature

## Context

{{include:../activeContext.md#Current Sprint}}

## Feature Goals

- Implement Stripe integration
- Support multiple payment methods
- Add payment history tracking

## Progress

- [x] Design API contracts
- [ ] Implement Stripe SDK
- [ ] Create payment models
- [ ] Add payment UI

## Technical Decisions

### Payment Provider: Stripe
Chosen for comprehensive API and strong security...
EOF

# Update activeContext to reference feature
echo "\n## Active Features\n\n{{include:features/payment-system.md}}" >> .cursor/memory-bank/activeContext.md
```

### Merge Conflict Resolution

**Memory Bank Merge Strategy (.gitattributes):**

```
.cursor/memory-bank/*.md merge=memory-bank-merge
```

**Custom Merge Driver (.git/config):**

```ini
[merge "memory-bank-merge"]
    name = Memory Bank intelligent merge
    driver = cortex merge-driver %O %A %B %P
```

**Merge Script (scripts/memory-bank-merge.sh):**

```bash
#!/bin/bash
# Memory Bank merge driver
BASE=$1   # %O - ancestor version
LOCAL=$2  # %A - current version
REMOTE=$3 # %B - other branch version
PATH=$4   # %P - file path

# Use Cortex merge logic
cortex merge_files \
  --base="$BASE" \
  --local="$LOCAL" \
  --remote="$REMOTE" \
  --strategy=semantic \
  --output="$LOCAL"

# Return 0 for clean merge, 1 for conflict
exit $?
```

---

## Custom Rule Creation

### Creating Custom Rules Repository

**Initialize Rules Repository:**

```bash
# Create new rules repository
mkdir memory-bank-rules && cd memory-bank-rules
git init

# Create structure
mkdir -p rules/{coding,documentation,architecture,testing}
mkdir -p patterns/{design,implementation}
mkdir -p templates/{projects,features}

# Create rule file
cat > rules/coding/typescript-standards.md <<EOF
# TypeScript Coding Standards

## File Organization

- One component per file
- Exports at bottom
- Imports organized: stdlib, third-party, local

## Naming Conventions

- PascalCase for components and types
- camelCase for functions and variables
- UPPER_CASE for constants

## Type Safety

- No \`any\` types (use \`unknown\` or proper types)
- Explicit return types for public functions
- Use discriminated unions for state

## Code Constraints

- Max file length: 400 lines
- Max function length: 30 lines
- Max cyclomatic complexity: 10
EOF

# Create pattern file
cat > patterns/design/event-driven.md <<EOF
# Event-Driven Architecture Pattern

## Overview

Event-driven architecture for decoupled microservices.

## Implementation

### Event Bus

Use message broker (RabbitMQ, Kafka) for async communication.

### Event Schema

\`\`\`typescript
interface Event {
  id: string;
  type: string;
  timestamp: Date;
  payload: Record<string, unknown>;
  metadata: EventMetadata;
}
\`\`\`

## Usage in Memory Bank

Reference in systemPatterns.md:

\`\`\`markdown
{{include:patterns/design/event-driven.md}}
\`\`\`
EOF

# Commit and push
git add .
git commit -m "Initial rules structure"
git remote add origin https://github.com/your-org/memory-bank-rules.git
git push -u origin main
```

### Rule Validation Schema

**Create validation schema (.cursor/rules-schema.json):**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["title", "category", "content"],
  "properties": {
    "title": {
      "type": "string",
      "minLength": 10,
      "maxLength": 100
    },
    "category": {
      "type": "string",
      "enum": ["coding", "documentation", "architecture", "testing", "process"]
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1
    },
    "content": {
      "type": "object",
      "required": ["overview", "rules"],
      "properties": {
        "overview": {"type": "string"},
        "rules": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "description", "severity"],
            "properties": {
              "id": {"type": "string", "pattern": "^[A-Z]{2,4}[0-9]{3}$"},
              "description": {"type": "string"},
              "severity": {"enum": ["error", "warning", "info"]},
              "examples": {
                "type": "object",
                "properties": {
                  "good": {"type": "array", "items": {"type": "string"}},
                  "bad": {"type": "array", "items": {"type": "string"}}
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Auto-Generated Rules

**Generate rules from codebase analysis:**

```python
# scripts/generate-rules.py
import ast
import json
from pathlib import Path

def analyze_codebase(src_dir: str) -> dict:
    """Analyze codebase and generate coding rules."""
    patterns = {
        "naming_conventions": [],
        "common_imports": [],
        "design_patterns": []
    }

    for py_file in Path(src_dir).rglob("*.py"):
        with open(py_file) as f:
            tree = ast.parse(f.read())

        # Analyze naming patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                patterns["naming_conventions"].append({
                    "type": "class",
                    "name": node.name,
                    "pattern": "PascalCase" if node.name[0].isupper() else "invalid"
                })

    return patterns

def generate_rules(patterns: dict, output_dir: str):
    """Generate rule files from patterns."""
    rules_md = f"""# Auto-Generated Coding Rules

## Naming Conventions

Based on analysis of {len(patterns['naming_conventions'])} classes:

- Classes: PascalCase (detected: 98% compliance)
- Functions: snake_case (detected: 95% compliance)
- Constants: UPPER_CASE (detected: 92% compliance)

## Common Patterns

{json.dumps(patterns, indent=2)}
"""

    Path(output_dir).mkdir(exist_ok=True)
    with open(f"{output_dir}/auto-generated-rules.md", "w") as f:
        f.write(rules_md)

if __name__ == "__main__":
    patterns = analyze_codebase("src/")
    generate_rules(patterns, ".cursor/rules")
```

---

## Advanced Transclusion Strategies

### Conditional Transclusion

**Environment-Specific Content:**

```markdown
<!-- systemPatterns.md -->
# System Patterns

## Architecture

{{include:architecture/base.md}}

## Environment-Specific Patterns

{{include:architecture/prod.md#if:ENVIRONMENT=production}}
{{include:architecture/dev.md#if:ENVIRONMENT=development}}
```

### Parameterized Transclusion

```markdown
<!-- Template file: templates/api-endpoint.md -->
# API Endpoint: ${ENDPOINT_NAME}

## URL

`${HTTP_METHOD} ${ENDPOINT_PATH}`

## Parameters

${PARAMETERS}

## Response

${RESPONSE_SCHEMA}

---

<!-- Usage in systemPatterns.md -->
{{include:templates/api-endpoint.md
  | ENDPOINT_NAME=User Login
  | HTTP_METHOD=POST
  | ENDPOINT_PATH=/api/v1/auth/login
  | PARAMETERS=username, password
  | RESPONSE_SCHEMA={"token": "string"}
}}
```

### Filtered Transclusion

```markdown
<!-- Include specific sections with filtering -->
{{include:systemPatterns.md#Architecture | exclude:Implementation Details}}

<!-- Include with line range -->
{{include:techContext.md#Tech Stack | lines:1-20}}

<!-- Include with regex filter -->
{{include:progress.md | filter:TODO|IN_PROGRESS}}
```

### Computed Transclusion

```markdown
<!-- Aggregate content from multiple files -->
{{aggregate:roles/*/progress.md#Current Sprint | format:table}}

<!-- Result: -->
| Role | Current Sprint |
|------|----------------|
| Frontend | Component Library |
| Backend | API Refactoring |
| DevOps | K8s Migration |
```

### Transclusion with Transformation

```json
{
  "transclusion": {
    "transformations": {
      "code_blocks": {
        "syntax_highlight": true,
        "line_numbers": true,
        "max_lines": 50
      },
      "tables": {
        "format": "github",
        "align": "left"
      },
      "links": {
        "resolve_relative": true,
        "validate": true
      }
    }
  }
}
```

---

## Cross-Project Memory Banks

### Shared Knowledge Base

Create a centralized knowledge base across multiple projects:

```
central-knowledge-base/
├── .cursor/memory-bank/
│   ├── company/
│   │   ├── mission.md
│   │   ├── values.md
│   │   └── processes.md
│   ├── engineering/
│   │   ├── standards.md
│   │   ├── patterns.md
│   │   └── best-practices.md
│   ├── product/
│   │   ├── strategy.md
│   │   └── roadmap.md
│   └── security/
│       ├── policies.md
│       └── procedures.md
```

**Project Configuration:**

```json
{
  "shared_knowledge_base": {
    "enabled": true,
    "repository": "https://github.com/company/knowledge-base.git",
    "mount_point": ".cursor/shared",
    "sync_mode": "read_only",
    "cache_locally": true
  },
  "transclusion": {
    "search_paths": [
      ".cursor/memory-bank",
      ".cursor/shared/memory-bank"
    ]
  }
}
```

**Usage in Project:**

```markdown
<!-- projectBrief.md -->
# Project Brief

## Company Context

{{include:../../shared/memory-bank/company/mission.md}}

## Engineering Standards

{{include:../../shared/memory-bank/engineering/standards.md}}
```

---

## Memory Bank as Code

### Infrastructure as Code for Memory Banks

```python
# memory-bank-config.py
from dataclasses import dataclass
from typing import List

@dataclass
class MemoryBankConfig:
    """Code-based Memory Bank configuration."""

    project_name: str
    core_files: List[str]
    validation_rules: dict
    token_budget: int

    def to_json(self) -> dict:
        return {
            "project_name": self.project_name,
            "memory_bank": {
                "core_files": self.core_files,
                "validation": self.validation_rules,
                "token_budget": self.token_budget
            }
        }

# Define configuration
config = MemoryBankConfig(
    project_name="my-project",
    core_files=[
        "projectBrief.md",
        "systemPatterns.md",
        "techContext.md"
    ],
    validation_rules={
        "schema_validation": {"enabled": True},
        "quality_threshold": 8.0
    },
    token_budget=100000
)

# Generate configuration file
import json
with open(".cursor/memory-bank-config.json", "w") as f:
    json.dump(config.to_json(), f, indent=2)
```

### Template-Based Generation

```yaml
# memory-bank-template.yml
project:
  name: ${PROJECT_NAME}
  type: ${PROJECT_TYPE}

memory_bank:
  structure: ${STRUCTURE_TYPE}
  core_files:
    - projectBrief.md
    - productContext.md
    - systemPatterns.md
    - techContext.md

  optional_files:
    - progress.md: ${{ PROJECT_TYPE == 'web' }}
    - roadmap.md: ${{ PROJECT_TYPE == 'web' }}
    - infrastructure.md: ${{ PROJECT_TYPE == 'backend' }}

  validation:
    enabled: true
    rules: ${VALIDATION_RULES}

  token_budget:
    max_total: ${{ 100000 if PROJECT_TYPE == 'web' else 50000 }}
```

---

## Progressive Enhancement Patterns

### Lazy Loading Configuration

```json
{
  "progressive_loading": {
    "enabled": true,
    "strategy": "priority",
    "priority_files": [
      "projectBrief.md",
      "activeContext.md"
    ],
    "load_on_demand": [
      "systemPatterns.md",
      "techContext.md"
    ],
    "defer_loading": [
      "roadmap.md",
      "progress.md"
    ],
    "batch_size": 3,
    "load_delay_ms": 100
  }
}
```

### Context-Aware Loading

```markdown
<!-- Load different content based on context -->
{{load:activeContext.md#if:developing}}
{{load:roadmap.md#if:planning}}
{{load:progress.md#if:reviewing}}
```

---

## Advanced Validation Patterns

### Custom Validation Rules

```python
# .cursor/validators/custom_validator.py
from typing import List, Dict

class CustomValidator:
    """Custom validation rules for Memory Bank."""

    def validate_api_documentation(self, content: str) -> List[str]:
        """Ensure API endpoints are documented."""
        errors = []

        # Check for required sections
        required_sections = ["Endpoints", "Authentication", "Error Codes"]
        for section in required_sections:
            if f"## {section}" not in content:
                errors.append(f"Missing required section: {section}")

        # Check for endpoint documentation format
        if "Endpoints" in content:
            # Validate endpoint format: METHOD /path
            import re
            endpoints = re.findall(r'`(GET|POST|PUT|DELETE|PATCH) (/[^\s`]+)`', content)
            if not endpoints:
                errors.append("No API endpoints documented in correct format")

        return errors

    def validate_code_examples(self, content: str) -> List[str]:
        """Ensure code examples are valid."""
        errors = []

        # Find code blocks
        import re
        code_blocks = re.findall(r'```(\w+)\n(.*?)```', content, re.DOTALL)

        for lang, code in code_blocks:
            if lang == "python":
                # Validate Python syntax
                try:
                    compile(code, '<string>', 'exec')
                except SyntaxError as e:
                    errors.append(f"Invalid Python code: {e}")

        return errors
```

**Register Custom Validator:**

```json
{
  "validation": {
    "custom_validators": [
      {
        "name": "api_documentation",
        "module": ".cursor.validators.custom_validator",
        "class": "CustomValidator",
        "method": "validate_api_documentation",
        "files": ["systemPatterns.md", "techContext.md"]
      },
      {
        "name": "code_examples",
        "module": ".cursor.validators.custom_validator",
        "class": "CustomValidator",
        "method": "validate_code_examples",
        "files": ["*.md"]
      }
    ]
  }
}
```

---

## Best Practices Summary

### Do's

- ✅ Use hierarchical structure for monorepos
- ✅ Implement CI/CD validation for Memory Bank changes
- ✅ Create role-based access for large teams
- ✅ Use shared rules repositories for consistency
- ✅ Implement custom validators for domain-specific needs
- ✅ Use transclusion to maintain DRY principle
- ✅ Configure progressive loading for large codebases
- ✅ Version control Memory Bank configurations

### Don'ts

- ❌ Don't duplicate content across files
- ❌ Don't skip validation in CI/CD pipelines
- ❌ Don't hardcode environment-specific content
- ❌ Don't mix concerns in Memory Bank files
- ❌ Don't exceed token budgets without optimization
- ❌ Don't ignore quality metrics
- ❌ Don't bypass validation rules

---

## Troubleshooting

### Common Issues

**Issue: Memory Bank sync conflicts in multi-repo setup**

Solution:
```bash
# Reset to shared state
cortex sync_shared_rules --force --strategy=theirs

# Or use three-way merge
cortex merge_rules --base=shared --local=current --remote=incoming
```

**Issue: Transclusion loops detected**

Solution:
```json
{
  "transclusion": {
    "max_depth": 5,
    "detect_loops": true,
    "break_on_loop": true
  }
}
```

**Issue: CI/CD validation timeout**

Solution:
```json
{
  "validation": {
    "timeout_seconds": 300,
    "parallel_validation": true,
    "cache_results": true
  }
}
```

---

## Next Steps

- Review [Performance Tuning Guide](./performance-tuning.md) for optimization
- Check [Extension Development Guide](./extension-development.md) for customization
- See [Configuration Guide](../configuration.md) for detailed settings
- Read [Troubleshooting Guide](../troubleshooting.md) for common issues
