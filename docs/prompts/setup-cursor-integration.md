# Setup Cursor Integration

This prompt template guides you through setting up Cursor IDE integration.

## Prerequisites

- Cortex server installed and configured
- Project structure setup
- Cursor IDE installed

## Prompt

```
Please setup Cursor IDE integration in my project at [PROJECT_ROOT].

I need you to:
1. Create .cursor/ configuration directory
2. Generate Cursor-specific config files
3. Setup MCP server configuration
4. Configure memory bank integration
5. Setup rules and context loading
6. Test the integration
```

## What Happens

The assistant will:

1. Create `.cursor/` directory structure
2. Generate configuration files:
   - `.cursor/config.json` - IDE settings
   - `.cursor/mcp.json` - MCP server config
   - `.cursor/rules/` - Rule files
3. Configure Cortex server
4. Setup context loading preferences
5. Test connection to MCP server
6. Report setup status

## Expected Output

### Successful Setup

```json
{
  "status": "success",
  "message": "Cursor integration setup successfully",
  "config_files": [
    ".cursor/config.json",
    ".cursor/mcp.json"
  ],
  "mcp_server": {
    "name": "memory-bank-helper",
    "status": "connected",
    "tools_available": 25
  }
}
```

### Already Configured

```json
{
  "status": "already_configured",
  "message": "Cursor integration already setup",
  "config_location": ".cursor/",
  "suggestion": "Use check_structure_health to validate"
}
```

### Failed Setup

```json
{
  "status": "failed",
  "message": "Failed to setup Cursor integration",
  "error": "Could not create .cursor/mcp.json",
  "suggestion": "Check file permissions"
}
```

## Configuration Files

### .cursor/config.json

```json
{
  "memory_bank": {
    "enabled": true,
    "location": "memory-bank/",
    "auto_load": true
  },
  "rules": {
    "location": ".cursor/rules/",
    "auto_index": true
  }
}
```

### .cursor/mcp.json

```json
{
  "mcpServers": {
    "memory-bank-helper": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/igrechuhin/cortex.git",
        "cortex"
      ]
    }
  }
}
```

## Features Enabled

After setup, you'll have:

- **Memory Bank tools** - All 25 MCP tools available
- **Rules integration** - Project rules auto-loaded
- **Context optimization** - Smart context loading
- **Link validation** - Automatic transclusion
- **Quality metrics** - Code quality scoring

## Post-Setup

After successful setup:

1. Restart Cursor IDE to load configuration
2. Verify MCP server appears in Cursor's tool list
3. Test a Memory Bank tool (e.g., `get_memory_bank_stats`)
4. Check that rules are indexed
5. Verify context loading works

## Troubleshooting

### MCP Server Not Connecting

```
Please check the MCP server configuration in .cursor/mcp.json.
The server should be running and accessible.
```

### Tools Not Appearing

```
Please verify that the MCP server is properly registered.
Check Cursor's settings → MCP Servers.
```

### Configuration Errors

```
Please validate the configuration files:
1. .cursor/config.json syntax
2. .cursor/mcp.json format
3. File permissions
```

## Testing the Setup

Test your integration:

```
Please test my Cursor integration by:
1. Getting memory bank stats
2. Validating the structure
3. Reading a memory bank file
```

This will verify all tools are working correctly.
