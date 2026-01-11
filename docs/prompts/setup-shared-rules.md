# Setup Shared Rules

This prompt template guides you through setting up shared rules via Git submodule.

## Prerequisites

- Cortex server installed and configured
- Memory Bank initialized
- Git repository initialized
- Shared rules repository URL

## Prompt

```
Please setup shared rules in my project at [PROJECT_ROOT].

I want to use shared rules from: [SHARED_RULES_REPO_URL]

I need you to:
1. Add the shared rules repository as a Git submodule
2. Clone it to .cortex/synapse/
3. Create the rules index
4. Validate the rules structure
5. Merge shared rules with my local rules
```

## What Happens

The assistant will:

1. Run `git submodule add [URL] .cortex/synapse/`
2. Initialize and update the submodule
3. Index all rules from the shared repository
4. Validate rule format and content
5. Merge with existing local rules
6. Report setup status

## Expected Output

### Successful Setup

```json
{
  "status": "success",
  "message": "Shared rules setup successfully",
  "shared_rules_path": ".cursor/rules/shared/",
  "rules_count": 15,
  "submodule_url": "https://github.com/org/shared-rules.git",
  "commit": "abc1234"
}
```

### Already Exists

```json
{
  "status": "already_exists",
  "message": "Shared rules already configured",
  "shared_rules_path": ".cursor/rules/shared/",
  "suggestion": "Use sync_shared_rules to update"
}
```

### Failed Setup

```json
{
  "status": "failed",
  "message": "Failed to setup shared rules",
  "error": "Git submodule command failed: ...",
  "suggestion": "Check repository URL and Git configuration"
}
```

## Shared Rules Structure

The shared rules repository should have this structure:

```
shared-rules/
├── README.md
├── python-security.mdc
├── python-testing-standards.mdc
├── no-test-skipping.mdc
└── ... other rule files
```

## Configuration

You can configure shared rules behavior:

- **Auto-sync**: Automatically pull updates (default: false)
- **Conflict resolution**: How to handle conflicts (default: "local_wins")
- **Selective merge**: Which rules to include (default: all)

## Post-Setup

After successful setup:

1. Review merged rules in `.cortex/synapse/`
2. Use `sync_shared_rules` to pull updates
3. Use `get_rules_with_context` for context-aware rule retrieval
4. Customize merge behavior if needed

## Updating Shared Rules

To update shared rules later:

```
Please sync my shared rules from the remote repository.
```

This will pull the latest changes from the shared rules repository.
