# Phase 6: Shared Rules Repository

## Overview

Enable cross-project rule sharing through a centralized rules repository. When rules evolve in one project, they automatically propagate to all other projects using the same rule set.

## Problem Statement

Users want to:

1. Maintain consistent coding standards across multiple projects
2. Evolve rules in one project and have them propagate to others
3. Share rules across teams (iOS/Swift, Python, etc.)
4. Have context-aware rule loading (generic + language-specific)
5. Allow project-specific overrides without breaking shared rules

## Solution: Hybrid Git Submodule + Smart MCP Integration

### Architecture

```text
Project A
├── memory-bank/
├── .cursorrules/              (Project-specific rules)
│   └── project-overrides.md
├── .shared-rules/             (Git submodule → shared-rules repo)
│   ├── generic/
│   │   ├── coding-standards.md
│   │   ├── documentation.md
│   │   └── testing.md
│   ├── python/
│   │   ├── style-guide.md
│   │   ├── best-practices.md
│   │   └── security.md
│   ├── swift/
│   │   ├── naming.md
│   │   ├── patterns.md
│   │   └── ui-guidelines.md
│   └── rules-manifest.json    (Metadata about rules)
└── .memory-bank-optimization.json

Project B (shares same .shared-rules submodule)
├── memory-bank/
├── .cursorrules/
├── .shared-rules/             (Same submodule)
└── .memory-bank-optimization.json
```

### Shared Rules Repository Structure

```text
shared-rules/ (separate git repo)
├── README.md
├── rules-manifest.json        (Metadata about all rules)
├── generic/                   (Always included)
│   ├── coding-standards.md
│   ├── documentation.md
│   ├── testing.md
│   ├── code-review.md
│   └── git-workflow.md
├── python/
│   ├── style-guide.md
│   ├── type-hints.md
│   ├── async-patterns.md
│   ├── testing.md
│   └── packaging.md
├── swift/
│   ├── naming-conventions.md
│   ├── architecture.md
│   ├── ui-guidelines.md
│   ├── testing.md
│   └── performance.md
├── javascript/
│   └── ...
├── rust/
│   └── ...
└── development-practices/     (Process rules)
    ├── agile.md
    ├── planning.md
    └── deployment.md
```

### rules-manifest.json

```json
{
  "version": "1.0",
  "last_updated": "2025-12-20T10:00:00Z",
  "categories": {
    "generic": {
      "description": "Universal coding standards",
      "always_include": true,
      "rules": [
        {
          "file": "coding-standards.md",
          "priority": 100,
          "keywords": ["code", "standards", "quality"],
          "applies_to": ["*"]
        },
        {
          "file": "documentation.md",
          "priority": 90,
          "keywords": ["docs", "comments", "readme"],
          "applies_to": ["*"]
        }
      ]
    },
    "python": {
      "description": "Python-specific rules",
      "always_include": false,
      "triggers": ["*.py", "python", "django", "flask"],
      "rules": [
        {
          "file": "style-guide.md",
          "priority": 100,
          "keywords": ["python", "pep8", "style"]
        }
      ]
    },
    "swift": {
      "description": "Swift/iOS rules",
      "always_include": false,
      "triggers": ["*.swift", "ios", "swiftui", "uikit"],
      "rules": [...]
    }
  }
}
```

## Implementation Plan

### 1. Enhanced Configuration (optimization_config.py)

Add shared rules configuration:

```json
{
  "rules": {
    "enabled": true,

    // Local project rules (existing)
    "local_rules_folder": ".cursorrules",

    // Shared rules (NEW)
    "shared_rules_enabled": true,
    "shared_rules_folder": ".shared-rules",
    "shared_rules_repo": "git@github.com:yourorg/shared-rules.git",
    "auto_sync_shared_rules": true,
    "sync_interval_minutes": 60,

    // Rule loading behavior (NEW)
    "rule_priority": "local_overrides_shared",  // or "shared_overrides_local"
    "context_aware_loading": true,
    "always_include_generic": true,

    // Existing
    "reindex_interval_minutes": 30,
    "max_rules_tokens": 10000,
    "min_relevance_score": 0.3,

    // NEW: Context detection
    "context_detection": {
      "enabled": true,
      "detect_from_task": true,
      "detect_from_files": true,
      "detect_from_git": true
    }
  }
}
```

### 2. New Module: shared_rules_manager.py (~500 lines)

**Key Features:**

```python
class SharedRulesManager:
    """Manage shared rules repository with git integration."""

    async def initialize_shared_rules(
        self,
        repo_url: str,
        local_path: Path
    ) -> Dict:
        """
        Initialize shared rules as git submodule.

        - Check if submodule exists
        - If not, run: git submodule add <repo_url> <local_path>
        - If exists, run: git submodule update --remote
        """

    async def sync_shared_rules(
        self,
        pull: bool = True,
        push: bool = False
    ) -> Dict:
        """
        Sync shared rules repository.

        pull: Pull latest changes from remote
        push: Push local changes to remote
        """

    async def load_rules_manifest(self) -> Dict:
        """Load and parse rules-manifest.json."""

    async def detect_context(
        self,
        task_description: str,
        project_files: List[Path]
    ) -> Dict:
        """
        Detect context for intelligent rule loading.

        Returns:
        {
            "languages": ["python", "javascript"],
            "frameworks": ["django", "react"],
            "task_type": "testing",
            "categories_to_load": ["generic", "python", "testing"]
        }
        """

    async def get_relevant_categories(
        self,
        context: Dict
    ) -> List[str]:
        """
        Get relevant rule categories based on context.

        Example:
        - Always include "generic"
        - If working on Python file, include "python"
        - If task mentions testing, include "testing"
        """

    async def merge_rules(
        self,
        shared_rules: List[Dict],
        local_rules: List[Dict],
        priority: str
    ) -> List[Dict]:
        """
        Merge shared and local rules based on priority.

        priority: "local_overrides_shared" or "shared_overrides_local"
        """

    async def update_shared_rule(
        self,
        category: str,
        file: str,
        content: str,
        commit_message: str
    ) -> Dict:
        """
        Update a shared rule and commit/push to remote.

        Workflow:
        1. Update file in .shared-rules/
        2. git add <file>
        3. git commit -m <message>
        4. git push
        """

    async def create_shared_rule(
        self,
        category: str,
        filename: str,
        content: str,
        metadata: Dict
    ) -> Dict:
        """
        Create a new shared rule and update manifest.
        """
```

### 3. Enhanced rules_manager.py (~200 lines of changes)

Integrate with SharedRulesManager:

```python
class RulesManager:
    """Enhanced to support both local and shared rules."""

    def __init__(self, ..., shared_rules_manager: Optional[SharedRulesManager] = None):
        self.shared_rules_manager = shared_rules_manager

    async def get_relevant_rules(
        self,
        task_description: str,
        max_tokens: int = 10000,
        min_relevance_score: float = 0.3,
        project_files: Optional[List[Path]] = None
    ) -> Dict:
        """
        Enhanced to intelligently load rules from both sources.

        Returns:
        {
            "generic_rules": [...],      # Always included
            "language_rules": [...],     # Context-specific
            "local_rules": [...],        # Project-specific
            "total_tokens": 8500,
            "context": {
                "detected_languages": ["python"],
                "detected_frameworks": ["django"],
                "task_type": "testing"
            }
        }
        """

        # 1. Detect context
        context = await self.shared_rules_manager.detect_context(
            task_description,
            project_files
        )

        # 2. Load generic rules (always)
        generic_rules = await self.shared_rules_manager.load_category("generic")

        # 3. Load context-specific rules
        language_rules = []
        for lang in context["detected_languages"]:
            rules = await self.shared_rules_manager.load_category(lang)
            language_rules.extend(rules)

        # 4. Load local project rules
        local_rules = await self._get_local_rules(task_description)

        # 5. Merge and prioritize
        all_rules = await self.shared_rules_manager.merge_rules(
            shared_rules=generic_rules + language_rules,
            local_rules=local_rules,
            priority=self.config.get("rule_priority")
        )

        # 6. Score and select within token budget
        selected_rules = await self._select_within_budget(
            all_rules,
            task_description,
            max_tokens,
            min_relevance_score
        )

        return {
            "generic_rules": [r for r in selected_rules if r["category"] == "generic"],
            "language_rules": [r for r in selected_rules if r["category"] in context["detected_languages"]],
            "local_rules": [r for r in selected_rules if r["source"] == "local"],
            "total_tokens": sum(r["tokens"] for r in selected_rules),
            "context": context
        }
```

### 4. New MCP Tools (4 tools)

#### 1. `setup_shared_rules(repo_url, local_path)`

Initialize shared rules repository as git submodule.

```json
{
  "status": "success",
  "action": "initialized",
  "repo_url": "git@github.com:yourorg/shared-rules.git",
  "local_path": ".shared-rules",
  "submodule_added": true,
  "initial_sync": true,
  "categories_found": ["generic", "python", "swift"]
}
```

#### 2. `sync_shared_rules(pull, push)`

Sync shared rules with remote repository.

```json
{
  "status": "success",
  "pulled": true,
  "pushed": false,
  "changes": {
    "added": ["python/new-rule.md"],
    "modified": ["generic/coding-standards.md"],
    "deleted": []
  },
  "reindex_triggered": true
}
```

#### 3. `update_shared_rule(category, file, content, commit_message)`

Update a shared rule and push to all projects.

```json
{
  "status": "success",
  "category": "python",
  "file": "style-guide.md",
  "committed": true,
  "pushed": true,
  "commit_hash": "abc123",
  "message": "Added type hints guidelines"
}
```

#### 4. `get_rules_with_context(task_description, project_files)`

Get intelligently selected rules based on task context.

```json
{
  "status": "success",
  "task_description": "Implement JWT authentication in Django",
  "context": {
    "detected_languages": ["python"],
    "detected_frameworks": ["django"],
    "detected_files": ["*.py"],
    "task_type": "authentication"
  },
  "rules_loaded": {
    "generic": [
      {"file": "coding-standards.md", "tokens": 800, "priority": 100},
      {"file": "security.md", "tokens": 600, "priority": 95}
    ],
    "python": [
      {"file": "style-guide.md", "tokens": 1200, "priority": 100},
      {"file": "django-patterns.md", "tokens": 900, "priority": 90}
    ],
    "local": [
      {"file": "project-auth-rules.md", "tokens": 400, "priority": 80}
    ]
  },
  "total_tokens": 3900,
  "token_budget": 10000
}
```

### 5. Context Detection Algorithm

```python
async def detect_context(
    self,
    task_description: str,
    project_files: Optional[List[Path]] = None
) -> Dict:
    """
    Multi-signal context detection.
    """
    context = {
        "languages": set(),
        "frameworks": set(),
        "task_type": None,
        "categories_to_load": set(["generic"])  # Always include
    }

    # 1. Detect from task description
    task_lower = task_description.lower()

    # Language detection
    if any(word in task_lower for word in ["python", "django", "flask", "fastapi"]):
        context["languages"].add("python")
    if any(word in task_lower for word in ["swift", "swiftui", "ios", "uikit"]):
        context["languages"].add("swift")
    # ... more languages

    # Framework detection
    if "django" in task_lower:
        context["frameworks"].add("django")
    if "swiftui" in task_lower:
        context["frameworks"].add("swiftui")

    # Task type detection
    if any(word in task_lower for word in ["test", "testing", "pytest"]):
        context["task_type"] = "testing"
    if any(word in task_lower for word in ["auth", "authentication", "login"]):
        context["task_type"] = "authentication"

    # 2. Detect from project files (if provided)
    if project_files:
        for file_path in project_files:
            suffix = file_path.suffix
            if suffix == ".py":
                context["languages"].add("python")
            elif suffix == ".swift":
                context["languages"].add("swift")
            # ... more extensions

    # 3. Build categories to load
    context["categories_to_load"].update(context["languages"])
    if context["task_type"]:
        context["categories_to_load"].add(context["task_type"])

    return {
        "detected_languages": list(context["languages"]),
        "detected_frameworks": list(context["frameworks"]),
        "task_type": context["task_type"],
        "categories_to_load": list(context["categories_to_load"])
    }
```

## Workflow Examples

### Example 1: Initial Setup

```bash
# In Project A
git submodule add git@github.com:yourorg/shared-rules.git .shared-rules
git submodule update --init --recursive

# MCP will auto-detect and index
```

### Example 2: Evolve Rule in Project A

User works on Project A, discovers better Python pattern:

```python
# Via MCP tool
mcp.call_tool("update_shared_rule", {
    "category": "python",
    "file": "async-patterns.md",
    "content": "... updated content ...",
    "commit_message": "Add best practice for asyncio context managers"
})

# MCP automatically:
# 1. Updates .shared-rules/python/async-patterns.md
# 2. Commits to submodule
# 3. Pushes to remote
```

### Example 3: Sync in Project B

Later, user works on Project B:

```bash
# MCP auto-syncs (if enabled)
# Or manual:
mcp.call_tool("sync_shared_rules", {"pull": true})

# Now Project B has the updated Python rules
```

### Example 4: Context-Aware Loading

```python
# User asks: "Implement authentication in Swift"

mcp.call_tool("get_rules_with_context", {
    "task_description": "Implement JWT authentication in Swift iOS app",
    "project_files": ["*.swift"]
})

# MCP intelligently loads:
# - generic/coding-standards.md
# - generic/security.md
# - swift/authentication.md
# - swift/networking.md
# - development-practices/testing.md (if mentioned in rules)
#
# Does NOT load:
# - python/* (not relevant)
# - javascript/* (not relevant)
```

## Benefits

### 1. Cross-Project Consistency

- Same standards across all projects
- Rules evolve globally
- Team knowledge is centralized

### 2. Intelligent Context Loading

- Only loads relevant rules (saves tokens)
- Generic rules always included
- Language/framework-specific rules loaded automatically

### 3. Easy Maintenance

- Update once, propagate everywhere
- Standard git workflow
- Version controlled rules

### 4. Flexible Override System

- Project-specific rules can override shared rules
- Clear priority system
- Merge strategies configurable

### 5. Collaborative

- Multiple teams can contribute to shared rules
- PR-based rule updates
- Code review for rule changes

## Technical Considerations

### Git Operations

```python
# Initialize submodule
await self._run_git_command([
    "git", "submodule", "add",
    repo_url,
    local_path
])

# Update submodule
await self._run_git_command([
    "git", "submodule", "update", "--remote", "--merge"
])

# Commit and push changes
await self._run_git_command([
    "git", "-C", shared_rules_path,
    "add", file_path
])
await self._run_git_command([
    "git", "-C", shared_rules_path,
    "commit", "-m", commit_message
])
await self._run_git_command([
    "git", "-C", shared_rules_path,
    "push"
])
```

### Performance Optimization

- **Lazy loading**: Only load rules when needed
- **Caching**: Cache loaded rules and manifest
- **Incremental updates**: Only reindex changed files
- **Async operations**: All git operations are async

### Error Handling

- **Network failures**: Graceful fallback to cached rules
- **Merge conflicts**: User intervention required
- **Missing submodule**: Auto-initialize or warn user
- **Invalid manifest**: Use defaults and log error

## Migration Path

### Phase 1: Basic Submodule Support

- Add git submodule initialization
- Basic sync operations
- Load rules from submodule

### Phase 2: Context Detection

- Implement language detection
- Framework detection
- Task type detection

### Phase 3: Intelligent Merging

- Priority-based merging
- Override system
- Token-aware selection

### Phase 4: Push Changes

- Update shared rules from project
- Automatic commit and push
- Update manifest

## Configuration Example

```json
{
  "rules": {
    "enabled": true,

    "local_rules_folder": ".cursorrules",

    "shared_rules_enabled": true,
    "shared_rules_folder": ".shared-rules",
    "shared_rules_repo": "git@github.com:myorg/coding-rules.git",
    "auto_sync_shared_rules": true,
    "sync_interval_minutes": 60,

    "rule_priority": "local_overrides_shared",
    "context_aware_loading": true,
    "always_include_generic": true,

    "reindex_interval_minutes": 30,
    "max_rules_tokens": 10000,
    "min_relevance_score": 0.3,

    "context_detection": {
      "enabled": true,
      "detect_from_task": true,
      "detect_from_files": true,
      "language_keywords": {
        "python": ["python", "django", "flask", "fastapi", "pytest"],
        "swift": ["swift", "swiftui", "ios", "uikit", "combine"],
        "javascript": ["javascript", "react", "vue", "node", "typescript"]
      }
    }
  }
}
```

## Implementation Estimate

- **New Module**: `shared_rules_manager.py` (~500 lines)
- **Enhanced Module**: `rules_manager.py` (+200 lines)
- **Configuration**: `optimization_config.py` (+100 lines)
- **MCP Tools**: 4 new tools (~400 lines)
- **Tests**: Comprehensive test suite (~800 lines)
- **Documentation**: User guide and examples

**Total**: ~2,000 lines of new code
**Estimated Time**: 2-3 weeks

## Next Steps

1. Review and approve this plan
2. Create shared-rules repository template
3. Implement `shared_rules_manager.py`
4. Enhance `rules_manager.py` with context detection
5. Add MCP tools
6. Write tests
7. Document workflows

---

**Status**: Proposed
**Dependencies**: Phase 4 Enhancement (Custom Rules Integration) ✅
**Target**: Phase 6
