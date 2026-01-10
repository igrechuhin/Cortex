# Extension Development Guide

This guide covers creating custom extensions for Cortex, including custom MCP tools, managers, validators, and refactoring strategies.

## Table of Contents

1. [Extension Overview](#extension-overview)
2. [Creating Custom MCP Tools](#creating-custom-mcp-tools)
3. [MCP Protocol Implementation](#mcp-protocol-implementation)
4. [Adding New Managers](#adding-new-managers)
5. [Extending the Validation System](#extending-the-validation-system)
6. [Custom Refactoring Strategies](#custom-refactoring-strategies)
7. [Plugin Architecture](#plugin-architecture)
8. [Testing Extensions](#testing-extensions)
9. [Publishing Extensions](#publishing-extensions)
10. [Best Practices](#best-practices)

---

## Extension Overview

### Extension Types

Cortex supports several extension types:

| Extension Type | Purpose | Complexity | Examples |
|---------------|---------|------------|----------|
| **MCP Tools** | Add new MCP endpoints | Low | Custom analysis, export tools |
| **Managers** | Add core functionality | Medium | Custom storage backends |
| **Validators** | Add validation rules | Low | Domain-specific checks |
| **Refactoring Strategies** | Add refactoring logic | Medium | Custom code transformations |
| **Protocols** | Define interfaces | Medium | New abstraction layers |
| **Plugins** | Composite extensions | High | Complete feature modules |

### Extension Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tools Layer                      │
│              (User-facing API endpoints)                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Extension Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Custom Tools  │  │Custom Mgrs   │  │Custom Valid. │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Core Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │File System   │  │Dependency    │  │Version Mgr   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Development Environment Setup

```bash
# Clone repository
git clone https://github.com/igrechuhin/cortex.git
cd cortex

# Install development dependencies
uv sync --dev

# Create extension directory
mkdir -p extensions/my-extension
cd extensions/my-extension

# Create extension structure
mkdir -p {tools,managers,validators,tests}
touch {tools,managers,validators,tests}/__init__.py
```

---

## Creating Custom MCP Tools

### Basic MCP Tool

Create a new tool in `extensions/my-extension/tools/custom_tool.py`:

```python
"""Custom MCP tools for Memory Bank extensions."""

import json
from pathlib import Path
from typing import cast

from cortex.server import mcp
from cortex.managers.initialization import get_managers, get_project_root
from cortex.core.file_system import FileSystemManager


@mcp.tool()
async def my_custom_tool(
    project_root: str | None = None,
    param1: str = "default",
    param2: int = 42
) -> str:
    """Custom tool for specific functionality.

    This tool demonstrates how to create custom MCP tools that integrate
    with the Memory Bank system.

    Args:
        project_root: Optional path to project root directory
        param1: Description of parameter 1
        param2: Description of parameter 2

    Returns:
        JSON string with tool results.

    Example:
        ```json
        {
          "status": "success",
          "result": {
            "param1": "value",
            "param2": 42
          }
        }
        ```
    """
    try:
        # Get project root and managers
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        fs = cast(FileSystemManager, mgrs["fs"])

        # Your custom logic here
        result = await _custom_logic(fs, param1, param2)

        return json.dumps({
            "status": "success",
            "result": result
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


async def _custom_logic(
    fs: FileSystemManager,
    param1: str,
    param2: int
) -> dict[str, object]:
    """Private helper function with custom logic.

    Args:
        fs: File system manager for file operations
        param1: Parameter 1
        param2: Parameter 2

    Returns:
        Dictionary with results
    """
    # Example: Read a file
    memory_bank_path = fs.project_root / ".cursor" / "memory-bank"
    projectBrief = memory_bank_path / "projectBrief.md"

    if projectBrief.exists():
        content, _ = await fs.read_file(projectBrief)
        lines = content.split("\n")
    else:
        lines = []

    # Custom processing
    result = {
        "param1": param1,
        "param2": param2,
        "file_exists": projectBrief.exists(),
        "line_count": len(lines)
    }

    return result
```

### Advanced MCP Tool with Validation

```python
"""Advanced MCP tool with parameter validation and complex logic."""

from typing import Literal
from pydantic import BaseModel, Field, validator

from cortex.server import mcp
from cortex.managers.initialization import get_managers, get_project_root


class ToolParams(BaseModel):
    """Type-safe parameters for custom tool."""

    project_root: str | None = None
    operation: Literal["analyze", "transform", "export"] = "analyze"
    threshold: float = Field(ge=0.0, le=1.0, default=0.8)
    include_metadata: bool = True

    @validator("threshold")
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        return v


@mcp.tool()
async def advanced_custom_tool(
    project_root: str | None = None,
    operation: str = "analyze",
    threshold: float = 0.8,
    include_metadata: bool = True
) -> str:
    """Advanced tool with validation and complex operations.

    Args:
        project_root: Optional path to project root
        operation: Operation to perform (analyze|transform|export)
        threshold: Threshold value (0.0-1.0)
        include_metadata: Include metadata in results

    Returns:
        JSON string with operation results
    """
    try:
        # Validate parameters
        params = ToolParams(
            project_root=project_root,
            operation=operation,
            threshold=threshold,
            include_metadata=include_metadata
        )

        # Get managers
        root = get_project_root(params.project_root)
        mgrs = await get_managers(root)

        # Execute operation
        if params.operation == "analyze":
            result = await _analyze_operation(mgrs, params)
        elif params.operation == "transform":
            result = await _transform_operation(mgrs, params)
        elif params.operation == "export":
            result = await _export_operation(mgrs, params)
        else:
            raise ValueError(f"Unknown operation: {params.operation}")

        return json.dumps({
            "status": "success",
            "operation": params.operation,
            "result": result
        }, indent=2)

    except ValueError as e:
        return json.dumps({
            "status": "error",
            "error": f"Validation error: {str(e)}"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


async def _analyze_operation(
    mgrs: dict[str, object],
    params: ToolParams
) -> dict[str, object]:
    """Perform analysis operation."""
    # Your analysis logic here
    return {"analyzed": True, "threshold": params.threshold}


async def _transform_operation(
    mgrs: dict[str, object],
    params: ToolParams
) -> dict[str, object]:
    """Perform transformation operation."""
    # Your transformation logic here
    return {"transformed": True}


async def _export_operation(
    mgrs: dict[str, object],
    params: ToolParams
) -> dict[str, object]:
    """Perform export operation."""
    # Your export logic here
    return {"exported": True}
```

### Register Custom Tools

Create `extensions/my-extension/tools/__init__.py`:

```python
"""Custom tools package initialization."""

# Import all custom tools to register them with FastMCP
from .custom_tool import my_custom_tool
from .advanced_tool import advanced_custom_tool

__all__ = [
    "my_custom_tool",
    "advanced_custom_tool",
]
```

Update `src/cortex/__init__.py`:

```python
"""Cortex package initialization."""

# Import core modules
from cortex import tools

# Import extensions
try:
    from extensions.my_extension import tools as custom_tools
except ImportError:
    pass  # Extensions are optional

__version__ = "1.0.0"
```

---

## MCP Protocol Implementation

### Understanding MCP Protocol

MCP (Model Context Protocol) uses JSON-RPC 2.0 over stdio for communication:

```
┌─────────────┐                           ┌─────────────┐
│             │   JSON-RPC Request        │             │
│  MCP Client │ ───────────────────────>  │  MCP Server │
│ (Claude/IDE)│                           │  (FastMCP)  │
│             │   JSON-RPC Response       │             │
│             │ <─────────────────────────│             │
└─────────────┘                           └─────────────┘
```

### Protocol Messages

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "my_custom_tool",
    "arguments": {
      "project_root": "/path/to/project",
      "param1": "value"
    }
  }
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"status\": \"success\", ...}"
      }
    ]
  }
}
```

### Custom Protocol Handler

For advanced use cases, implement custom protocol handlers:

```python
"""Custom MCP protocol handler."""

from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions


class CustomProtocolHandler:
    """Custom protocol handler for specialized MCP operations."""

    def __init__(self, mcp_server: FastMCP):
        """Initialize handler with MCP server instance.

        Args:
            mcp_server: FastMCP server instance
        """
        self.mcp = mcp_server
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register custom protocol handlers."""
        # Register custom initialization
        self.mcp.server.on_initialize = self._on_initialize

        # Register custom request handlers
        self.mcp.server.request_handlers.update({
            "custom/operation": self._handle_custom_operation
        })

    async def _on_initialize(
        self,
        options: InitializationOptions
    ) -> dict[str, Any]:
        """Handle initialization with custom options.

        Args:
            options: Initialization options from client

        Returns:
            Server capabilities
        """
        return {
            "capabilities": {
                "tools": {"enabled": True},
                "resources": {"enabled": True},
                "custom": {"enabled": True}
            }
        }

    async def _handle_custom_operation(
        self,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle custom protocol operation.

        Args:
            params: Operation parameters

        Returns:
            Operation result
        """
        # Your custom protocol logic here
        return {"status": "success", "result": {}}
```

---

## Adding New Managers

### Manager Protocol

Create a protocol interface in `extensions/my-extension/managers/protocols.py`:

```python
"""Protocol definitions for custom managers."""

from pathlib import Path
from typing import Protocol


class CustomManagerProtocol(Protocol):
    """Protocol for custom manager functionality.

    This protocol defines the interface that custom managers must implement
    to integrate with the Memory Bank system.
    """

    project_root: Path

    async def initialize(self) -> None:
        """Initialize the manager.

        This method is called during system startup to set up any required
        resources, connections, or state.
        """
        ...

    async def cleanup(self) -> None:
        """Cleanup manager resources.

        This method is called during system shutdown to release resources,
        close connections, and perform cleanup.
        """
        ...

    async def custom_operation(self, param: str) -> dict[str, object]:
        """Perform a custom operation.

        Args:
            param: Operation parameter

        Returns:
            Dictionary with operation results
        """
        ...
```

### Manager Implementation

Create the manager in `extensions/my-extension/managers/custom_manager.py`:

```python
"""Custom manager implementation."""

import asyncio
from pathlib import Path
from typing import cast

from cortex.core.protocols.file_system import FileSystemProtocol


class CustomManager:
    """Custom manager for specialized functionality.

    This manager demonstrates how to create custom managers that integrate
    with the Memory Bank core system.

    Attributes:
        project_root: Root directory of the project
        fs: File system manager for file operations
    """

    def __init__(
        self,
        project_root: Path,
        fs: FileSystemProtocol
    ):
        """Initialize custom manager.

        Args:
            project_root: Root directory of the project
            fs: File system manager for file operations
        """
        self.project_root = project_root
        self.fs = fs
        self._initialized = False
        self._cache: dict[str, object] = {}

    async def initialize(self) -> None:
        """Initialize the manager.

        This method sets up any required resources, loads configuration,
        and prepares the manager for use.
        """
        if self._initialized:
            return

        # Load configuration
        config_path = self.project_root / ".cursor" / "custom-config.json"
        if config_path.exists():
            content, _ = await self.fs.read_file(config_path)
            import json
            self._config = json.loads(content)
        else:
            self._config = {}

        self._initialized = True

    async def cleanup(self) -> None:
        """Cleanup manager resources.

        This method releases resources and performs cleanup when the
        manager is no longer needed.
        """
        if not self._initialized:
            return

        # Clear cache
        self._cache.clear()

        # Save state if needed
        # await self._save_state()

        self._initialized = False

    async def custom_operation(self, param: str) -> dict[str, object]:
        """Perform a custom operation.

        Args:
            param: Operation parameter

        Returns:
            Dictionary with operation results

        Raises:
            RuntimeError: If manager is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Manager not initialized")

        # Check cache
        cache_key = f"op_{param}"
        if cache_key in self._cache:
            return cast(dict[str, object], self._cache[cache_key])

        # Perform operation
        result = await self._do_operation(param)

        # Cache result
        self._cache[cache_key] = result

        return result

    async def _do_operation(self, param: str) -> dict[str, object]:
        """Internal operation implementation.

        Args:
            param: Operation parameter

        Returns:
            Operation results
        """
        # Your custom logic here
        await asyncio.sleep(0.1)  # Simulate async work

        return {
            "param": param,
            "result": "operation completed",
            "timestamp": "2024-01-10T12:00:00Z"
        }
```

### Register Manager

Update `src/cortex/managers/initialization.py`:

```python
"""Manager initialization and dependency injection."""

from pathlib import Path
from typing import Any

from cortex.core.file_system import FileSystemManager
# ... other imports ...


async def get_managers(project_root: Path) -> dict[str, Any]:
    """Initialize all managers with dependency injection.

    Args:
        project_root: Root directory of the project

    Returns:
        Dictionary of initialized managers
    """
    # Initialize core managers
    fs = FileSystemManager(project_root)
    # ... other core managers ...

    # Initialize custom managers
    try:
        from extensions.my_extension.managers.custom_manager import CustomManager
        custom = CustomManager(project_root, fs)
        await custom.initialize()
    except ImportError:
        custom = None

    return {
        "fs": fs,
        # ... other managers ...
        "custom": custom,
    }
```

---

## Extending the Validation System

### Custom Validator

Create a validator in `extensions/my-extension/validators/custom_validator.py`:

```python
"""Custom validators for Memory Bank files."""

import re
from pathlib import Path
from typing import cast

from cortex.core.protocols.file_system import FileSystemProtocol
from cortex.validation.schema_validator import ValidationError


class CustomValidator:
    """Custom validator for domain-specific validation rules.

    This validator demonstrates how to create custom validation rules
    that check for domain-specific requirements.
    """

    def __init__(self, fs: FileSystemProtocol):
        """Initialize validator.

        Args:
            fs: File system manager for file operations
        """
        self.fs = fs

    async def validate_file(self, file_path: Path) -> list[ValidationError]:
        """Validate a file with custom rules.

        Args:
            file_path: Path to file to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[ValidationError] = []

        # Read file
        content, _ = await self.fs.read_file(file_path)

        # Run custom validation rules
        errors.extend(self._validate_required_sections(content, file_path))
        errors.extend(self._validate_code_blocks(content, file_path))
        errors.extend(self._validate_links(content, file_path))
        errors.extend(self._validate_custom_format(content, file_path))

        return errors

    def _validate_required_sections(
        self,
        content: str,
        file_path: Path
    ) -> list[ValidationError]:
        """Validate that required sections are present.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of validation errors
        """
        errors: list[ValidationError] = []

        # Define required sections by file type
        required_sections: dict[str, list[str]] = {
            "projectBrief.md": ["Overview", "Goals", "Team"],
            "systemPatterns.md": ["Architecture", "Design Patterns"],
            "techContext.md": ["Tech Stack", "Development Setup"]
        }

        file_name = file_path.name
        if file_name in required_sections:
            for section in required_sections[file_name]:
                pattern = rf'^#+\s+{re.escape(section)}'
                if not re.search(pattern, content, re.MULTILINE):
                    errors.append(ValidationError(
                        file=str(file_path),
                        line=0,
                        message=f"Missing required section: {section}",
                        severity="error"
                    ))

        return errors

    def _validate_code_blocks(
        self,
        content: str,
        file_path: Path
    ) -> list[ValidationError]:
        """Validate code blocks have language specifiers.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of validation errors
        """
        errors: list[ValidationError] = []

        # Find code blocks without language specifiers
        pattern = r'^```\s*$'
        matches = re.finditer(pattern, content, re.MULTILINE)

        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            errors.append(ValidationError(
                file=str(file_path),
                line=line_num,
                message="Code block missing language specifier",
                severity="warning"
            ))

        return errors

    def _validate_links(
        self,
        content: str,
        file_path: Path
    ) -> list[ValidationError]:
        """Validate markdown links are properly formatted.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of validation errors
        """
        errors: list[ValidationError] = []

        # Find broken markdown links
        pattern = r'\[([^\]]+)\]\(([^\)]*)\)'
        matches = re.finditer(pattern, content)

        for match in matches:
            link_text = match.group(1)
            link_url = match.group(2)

            if not link_url:
                line_num = content[:match.start()].count('\n') + 1
                errors.append(ValidationError(
                    file=str(file_path),
                    line=line_num,
                    message=f"Empty link URL for text: {link_text}",
                    severity="error"
                ))

        return errors

    def _validate_custom_format(
        self,
        content: str,
        file_path: Path
    ) -> list[ValidationError]:
        """Validate custom domain-specific format requirements.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of validation errors
        """
        errors: list[ValidationError] = []

        # Example: Check for TODO comments
        pattern = r'TODO:'
        matches = re.finditer(pattern, content)

        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            errors.append(ValidationError(
                file=str(file_path),
                line=line_num,
                message="TODO comment found - should be tracked in roadmap.md",
                severity="info"
            ))

        return errors
```

### Register Validator

Update validation configuration in `.memory-bank-validation.json`:

```json
{
  "schema_validation": {
    "enabled": true,
    "custom_validators": [
      {
        "name": "custom_validator",
        "module": "extensions.my_extension.validators.custom_validator",
        "class": "CustomValidator",
        "enabled": true
      }
    ]
  }
}
```

---

## Custom Refactoring Strategies

### Refactoring Strategy Implementation

Create a refactoring strategy in `extensions/my-extension/refactoring/custom_strategy.py`:

```python
"""Custom refactoring strategies."""

from pathlib import Path
from typing import Any

from cortex.core.protocols.file_system import FileSystemProtocol
from cortex.refactoring.refactoring_engine import RefactoringSuggestion


class CustomRefactoringStrategy:
    """Custom refactoring strategy for specialized transformations.

    This strategy demonstrates how to create custom refactoring logic
    that can suggest and execute code transformations.
    """

    def __init__(self, fs: FileSystemProtocol):
        """Initialize refactoring strategy.

        Args:
            fs: File system manager for file operations
        """
        self.fs = fs

    async def analyze(
        self,
        file_path: Path
    ) -> list[RefactoringSuggestion]:
        """Analyze file and generate refactoring suggestions.

        Args:
            file_path: Path to file to analyze

        Returns:
            List of refactoring suggestions
        """
        suggestions: list[RefactoringSuggestion] = []

        # Read file
        content, _ = await self.fs.read_file(file_path)

        # Analyze for custom patterns
        suggestions.extend(self._detect_long_sections(content, file_path))
        suggestions.extend(self._detect_duplication(content, file_path))
        suggestions.extend(self._detect_split_opportunities(content, file_path))

        return suggestions

    def _detect_long_sections(
        self,
        content: str,
        file_path: Path
    ) -> list[RefactoringSuggestion]:
        """Detect sections that are too long and suggest splitting.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of refactoring suggestions
        """
        suggestions: list[RefactoringSuggestion] = []

        # Parse sections
        sections = self._parse_sections(content)

        for section_name, section_content in sections.items():
            line_count = section_content.count('\n')

            if line_count > 100:
                suggestions.append(RefactoringSuggestion(
                    id=f"split_section_{section_name}",
                    type="split",
                    description=f"Split long section '{section_name}' ({line_count} lines)",
                    file=str(file_path),
                    severity="warning",
                    confidence=0.8,
                    changes=[{
                        "type": "split_section",
                        "section": section_name,
                        "target_file": f"{file_path.stem}-{section_name.lower().replace(' ', '-')}.md"
                    }]
                ))

        return suggestions

    def _detect_duplication(
        self,
        content: str,
        file_path: Path
    ) -> list[RefactoringSuggestion]:
        """Detect duplicated content and suggest consolidation.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of refactoring suggestions
        """
        suggestions: list[RefactoringSuggestion] = []

        # Your duplication detection logic here
        # For example, compare paragraphs and find similar content

        return suggestions

    def _detect_split_opportunities(
        self,
        content: str,
        file_path: Path
    ) -> list[RefactoringSuggestion]:
        """Detect opportunities to split file into multiple files.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of refactoring suggestions
        """
        suggestions: list[RefactoringSuggestion] = []

        # Calculate file metrics
        line_count = content.count('\n')
        section_count = len(self._parse_sections(content))

        if line_count > 500 and section_count > 10:
            suggestions.append(RefactoringSuggestion(
                id=f"split_file_{file_path.name}",
                type="split",
                description=f"Split large file ({line_count} lines, {section_count} sections)",
                file=str(file_path),
                severity="warning",
                confidence=0.9,
                changes=[{
                    "type": "split_file",
                    "strategy": "by_section",
                    "target_directory": file_path.parent / file_path.stem
                }]
            ))

        return suggestions

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Parse content into sections by heading.

        Args:
            content: File content

        Returns:
            Dictionary mapping section names to content
        """
        import re

        sections: dict[str, str] = {}
        current_section = "Introduction"
        current_content: list[str] = []

        for line in content.split('\n'):
            heading_match = re.match(r'^(#+)\s+(.+)$', line)
            if heading_match:
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)

                # Start new section
                current_section = heading_match.group(2)
                current_content = [line]
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections
```

---

## Plugin Architecture

### Plugin System

Create a plugin loader in `extensions/my-extension/plugin_loader.py`:

```python
"""Plugin system for Memory Bank extensions."""

import importlib
import sys
from pathlib import Path
from typing import Any, Protocol


class PluginProtocol(Protocol):
    """Protocol for Memory Bank plugins."""

    name: str
    version: str

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin."""
        ...

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        ...

    def get_tools(self) -> list[str]:
        """Get list of tools provided by this plugin."""
        ...


class PluginLoader:
    """Load and manage Memory Bank plugins."""

    def __init__(self, plugin_dir: Path):
        """Initialize plugin loader.

        Args:
            plugin_dir: Directory containing plugins
        """
        self.plugin_dir = plugin_dir
        self.plugins: dict[str, PluginProtocol] = {}

    async def load_plugins(self) -> None:
        """Discover and load all plugins."""
        if not self.plugin_dir.exists():
            return

        for plugin_path in self.plugin_dir.iterdir():
            if plugin_path.is_dir() and (plugin_path / "__init__.py").exists():
                await self._load_plugin(plugin_path)

    async def _load_plugin(self, plugin_path: Path) -> None:
        """Load a single plugin.

        Args:
            plugin_path: Path to plugin directory
        """
        plugin_name = plugin_path.name

        try:
            # Add plugin directory to sys.path
            if str(plugin_path.parent) not in sys.path:
                sys.path.insert(0, str(plugin_path.parent))

            # Import plugin module
            module = importlib.import_module(plugin_name)

            # Get plugin class
            if hasattr(module, "Plugin"):
                plugin_class = getattr(module, "Plugin")
                plugin = plugin_class()

                # Initialize plugin
                config = self._load_plugin_config(plugin_path)
                await plugin.initialize(config)

                # Register plugin
                self.plugins[plugin.name] = plugin

                print(f"Loaded plugin: {plugin.name} v{plugin.version}")

        except Exception as e:
            print(f"Failed to load plugin {plugin_name}: {e}")

    def _load_plugin_config(self, plugin_path: Path) -> dict[str, Any]:
        """Load plugin configuration.

        Args:
            plugin_path: Path to plugin directory

        Returns:
            Plugin configuration
        """
        config_file = plugin_path / "plugin.json"
        if config_file.exists():
            import json
            return json.loads(config_file.read_text())
        return {}

    async def shutdown_plugins(self) -> None:
        """Shutdown all loaded plugins."""
        for plugin in self.plugins.values():
            try:
                await plugin.shutdown()
            except Exception as e:
                print(f"Error shutting down plugin {plugin.name}: {e}")
```

### Example Plugin

Create a complete plugin in `extensions/my-plugin/`:

```python
# extensions/my-plugin/__init__.py
"""Example Memory Bank plugin."""

from typing import Any

from cortex.server import mcp


class Plugin:
    """Example plugin for Memory Bank."""

    name = "my-plugin"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize plugin.

        Args:
            config: Plugin configuration
        """
        self.config = config
        print(f"Initializing {self.name} v{self.version}")

        # Register tools
        self._register_tools()

    async def shutdown(self) -> None:
        """Shutdown plugin."""
        print(f"Shutting down {self.name}")

    def get_tools(self) -> list[str]:
        """Get list of tools provided by this plugin.

        Returns:
            List of tool names
        """
        return ["plugin_tool_1", "plugin_tool_2"]

    def _register_tools(self) -> None:
        """Register plugin tools with MCP server."""
        @mcp.tool()
        async def plugin_tool_1(param: str) -> str:
            """Example plugin tool 1."""
            return f"Tool 1 executed with param: {param}"

        @mcp.tool()
        async def plugin_tool_2(value: int) -> str:
            """Example plugin tool 2."""
            return f"Tool 2 executed with value: {value}"
```

Plugin configuration (`extensions/my-plugin/plugin.json`):

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Example Memory Bank plugin",
  "author": "Your Name",
  "dependencies": [],
  "config": {
    "enabled": true,
    "custom_setting": "value"
  }
}
```

---

## Testing Extensions

### Unit Tests

Create unit tests in `extensions/my-extension/tests/test_custom_manager.py`:

```python
"""Unit tests for custom manager."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from extensions.my_extension.managers.custom_manager import CustomManager


@pytest.fixture
def mock_fs():
    """Create mock file system."""
    fs = MagicMock()
    fs.read_file = AsyncMock(return_value=('{"key": "value"}', "hash123"))
    fs.write_file = AsyncMock(return_value="hash456")
    return fs


@pytest.fixture
def project_root(tmp_path):
    """Create temporary project root."""
    return tmp_path


@pytest.fixture
async def custom_manager(project_root, mock_fs):
    """Create custom manager instance."""
    manager = CustomManager(project_root, mock_fs)
    await manager.initialize()
    return manager


@pytest.mark.asyncio
async def test_initialize(custom_manager):
    """Test manager initialization."""
    assert custom_manager._initialized is True
    assert custom_manager._config is not None


@pytest.mark.asyncio
async def test_custom_operation(custom_manager):
    """Test custom operation."""
    result = await custom_manager.custom_operation("test_param")

    assert result["param"] == "test_param"
    assert result["result"] == "operation completed"
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_custom_operation_caching(custom_manager):
    """Test operation result caching."""
    # First call
    result1 = await custom_manager.custom_operation("test")

    # Second call (should use cache)
    result2 = await custom_manager.custom_operation("test")

    assert result1 == result2
    assert "op_test" in custom_manager._cache


@pytest.mark.asyncio
async def test_cleanup(custom_manager):
    """Test manager cleanup."""
    # Add some cache data
    await custom_manager.custom_operation("test")
    assert len(custom_manager._cache) > 0

    # Cleanup
    await custom_manager.cleanup()

    assert custom_manager._initialized is False
    assert len(custom_manager._cache) == 0
```

### Integration Tests

Create integration tests in `extensions/my-extension/tests/test_integration.py`:

```python
"""Integration tests for custom extension."""

import pytest
import json
from pathlib import Path

from cortex.managers.initialization import get_managers


@pytest.fixture
async def memory_bank_project(tmp_path):
    """Create temporary Memory Bank project."""
    project_root = tmp_path / "test-project"
    project_root.mkdir()

    # Create Memory Bank structure
    mb_dir = project_root / ".cursor" / "memory-bank"
    mb_dir.mkdir(parents=True)

    # Create basic files
    (mb_dir / "projectBrief.md").write_text("# Test Project")
    (mb_dir / "activeContext.md").write_text("# Active Context")

    return project_root


@pytest.mark.asyncio
async def test_custom_tool_integration(memory_bank_project):
    """Test custom tool integration with Memory Bank."""
    from extensions.my_extension.tools.custom_tool import my_custom_tool

    # Execute tool
    result_json = await my_custom_tool(
        project_root=str(memory_bank_project),
        param1="test",
        param2=42
    )

    result = json.loads(result_json)

    assert result["status"] == "success"
    assert result["result"]["param1"] == "test"
    assert result["result"]["param2"] == 42


@pytest.mark.asyncio
async def test_custom_manager_integration(memory_bank_project):
    """Test custom manager integration."""
    # Get managers (including custom manager)
    mgrs = await get_managers(memory_bank_project)

    assert "custom" in mgrs
    assert mgrs["custom"] is not None

    # Test custom manager operation
    custom = mgrs["custom"]
    result = await custom.custom_operation("integration_test")

    assert result["param"] == "integration_test"
```

### Test Configuration

Create pytest configuration (`extensions/my-extension/pytest.ini`):

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
```

---

## Publishing Extensions

### Package Structure

```
my-extension/
├── README.md
├── LICENSE
├── pyproject.toml
├── setup.py
├── extensions/
│   └── my_extension/
│       ├── __init__.py
│       ├── tools/
│       │   ├── __init__.py
│       │   └── custom_tool.py
│       ├── managers/
│       │   ├── __init__.py
│       │   └── custom_manager.py
│       ├── validators/
│       │   ├── __init__.py
│       │   └── custom_validator.py
│       └── tests/
│           ├── __init__.py
│           ├── test_custom_tool.py
│           └── test_custom_manager.py
└── docs/
    ├── index.md
    └── usage.md
```

### Package Configuration

Create `pyproject.toml`:

```toml
[project]
name = "cortex-my-extension"
version = "1.0.0"
description = "Custom extension for Cortex"
authors = [{name = "Your Name", email = "your.email@example.com"}]
readme = "README.md"
requires-python = ">=3.13"
license = {text = "MIT"}

dependencies = [
    "cortex>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "mypy>=1.0.0",
]

[project.urls]
Homepage = "https://github.com/yourusername/cortex-my-extension"
Repository = "https://github.com/yourusername/cortex-my-extension"
Documentation = "https://yourusername.github.io/cortex-my-extension"

[build-system]
requires = ["setuptools>=65.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["extensions.my_extension"]

[tool.pytest.ini_options]
testpaths = ["extensions/my_extension/tests"]
asyncio_mode = "auto"

[tool.black]
line-length = 88
target-version = ["py313"]

[tool.mypy]
python_version = "3.13"
strict = true
```

### Publishing to PyPI

```bash
# Build package
python -m build

# Upload to PyPI
python -m twine upload dist/*

# Or use poetry
poetry build
poetry publish
```

### Installation

Users can install your extension:

```bash
# From PyPI
pip install cortex-my-extension

# From source
pip install git+https://github.com/yourusername/cortex-my-extension.git

# Development install
git clone https://github.com/yourusername/cortex-my-extension.git
cd cortex-my-extension
pip install -e ".[dev]"
```

---

## Best Practices

### Extension Development Guidelines

1. **Follow Core Conventions**
   - Use same code style as core (Black, 88 chars)
   - Follow same patterns (async, dependency injection)
   - Use type hints (100% coverage)
   - Document everything (docstrings, examples)

2. **Protocol-Based Design**
   - Define protocols for interfaces
   - Use structural subtyping (PEP 544)
   - Avoid tight coupling to implementations

3. **Error Handling**
   - Use domain-specific exceptions
   - Provide helpful error messages
   - Log errors appropriately
   - Return JSON error responses

4. **Testing**
   - Write unit tests for all code
   - Include integration tests
   - Aim for >90% coverage
   - Test error cases

5. **Documentation**
   - Write clear docstrings
   - Include usage examples
   - Provide configuration examples
   - Document all parameters

6. **Performance**
   - Use async/await throughout
   - Cache expensive operations
   - Avoid blocking operations
   - Profile performance

### Security Considerations

1. **Input Validation**
   - Validate all external inputs
   - Use Pydantic for parameter validation
   - Check file paths for traversal attacks
   - Sanitize user-provided data

2. **File Operations**
   - Validate paths against project root
   - Use safe file operations
   - Check permissions
   - Handle race conditions

3. **Secrets**
   - Never hardcode credentials
   - Use environment variables
   - Support secret managers
   - Don't log sensitive data

---

## Next Steps

- Review [Advanced Patterns Guide](./advanced-patterns.md) for complex patterns
- Check [Performance Tuning Guide](./performance-tuning.md) for optimization
- See [API Documentation](../../api/tools.md) for tool reference
- Read [Contributing Guide](../../development/contributing.md) for contribution guidelines

---

## Resources

### Example Extensions

- [cortex-export](https://github.com/example/cortex-export) - Export Memory Bank to various formats
- [cortex-sync](https://github.com/example/cortex-sync) - Sync Memory Bank across repositories
- [cortex-analytics](https://github.com/example/cortex-analytics) - Advanced analytics and insights

### Documentation

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Python Async Programming](https://docs.python.org/3/library/asyncio.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)

### Community

- [GitHub Discussions](https://github.com/igrechuhin/cortex/discussions)
- [Discord Server](https://discord.gg/cortex)
- [Stack Overflow Tag](https://stackoverflow.com/questions/tagged/cortex)
