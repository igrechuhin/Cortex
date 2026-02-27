# Setup Synapse

This prompt template guides you through setting up Synapse (shared rules repository) via Git submodule.

## Prerequisites

- Cortex server installed and configured
- Memory Bank initialized (optional, but recommended)
- Git repository initialized
- Synapse repository URL (default provided)

## Prompt

```text
Please setup Synapse in my project.

I want to use Synapse from: https://github.com/igrechuhin/Synapse.git
```

Or with custom URL:

```text
Please setup Synapse in my project.

I want to use Synapse from: https://github.com/your-org/Synapse.git
```

## What Happens

The assistant will:

1. **Add Synapse as Git submodule**
   - Runs `git submodule add <synapse_repo_url> .cortex/synapse/`
   - Initializes and updates the submodule recursively

2. **Validate structure**
   - Checks that Synapse has `rules/` and `prompts/` subdirectories
   - Validates rules manifest (`rules/rules-manifest.json`)
   - Validates prompts manifest (`prompts/prompts-manifest.json`)

3. **Create rules index**
   - Indexes all rules from the Synapse repository
   - Makes rules available for context-aware retrieval

4. **Report setup status**
   - Reports number of rules and prompts found
   - Reports submodule commit hash
   - Confirms setup completion

## Expected Output

### Successful Setup

```json
{
  "status": "success",
  "message": "Synapse setup successfully",
  "synapse_path": ".cortex/synapse/",
  "rules_count": 42,
  "prompts_count": 15,
  "submodule_url": "https://github.com/igrechuhin/Synapse.git",
  "commit": "a1b2c3d4e5f6"
}
```

### Already Exists

```json
{
  "status": "already_exists",
  "message": "Synapse already configured",
  "synapse_path": ".cortex/synapse/",
  "submodule_url": "https://github.com/igrechuhin/Synapse.git",
  "commit": "a1b2c3d4e5f6",
  "suggestion": "Use synapse(operation=\"sync\") to update"
}
```

### Failed Setup

```json
{
  "status": "failed",
  "message": "Failed to setup Synapse",
  "error": "Git submodule command failed: ...",
  "suggestion": "Check repository URL and Git configuration"
}
```

## When This Prompt Appears

This prompt is **always available** (not conditionally registered). You can use it:

- During initial project setup (after `initialize`)
- On existing projects (to add Synapse later)
- To override the default Synapse URL
- To re-setup Synapse if it was removed

## Default URL

If no URL is provided, the prompt uses the default:

- `https://github.com/igrechuhin/Synapse.git`

You can override this by providing a custom URL parameter.

## Synapse Structure

The Synapse repository should have this structure:

```text
synapse/
├── LICENSE
├── README.md
├── rules/
│   ├── rules-manifest.json
│   ├── general/
│   │   ├── code-style.mdc
│   │   ├── security.mdc
│   │   └── ...
│   ├── python/
│   │   ├── async-patterns.mdc
│   │   ├── type-hints.mdc
│   │   └── ...
│   └── ...
└── prompts/
    ├── prompts-manifest.json
    ├── general/
    │   ├── commit.md
    │   ├── review.md
    │   └── ...
    └── ...
```

## Post-Setup

After successful setup:

1. **Rules are indexed** - Use `rules(operation="get_relevant", ...)` to retrieve rules
2. **Prompts are available** - Synapse prompts (commit, review, implement, plan) are registered
3. **Sync updates** - Use `synapse(operation="sync")` to pull latest changes from remote
4. **Customize** - You can customize rules locally (they won't be overwritten by sync)

## Updating Synapse

To update Synapse later:

```text
Please sync my Synapse repository with the remote.
```

Or use the `synapse(operation="sync")` MCP tool to pull the latest changes.

## Related Prompts

- **initialize** - Complete project initialization (optionally includes Synapse setup)
- **migrate** - Migrate legacy structure (may include Synapse migration)
