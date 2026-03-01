"""Phase 2: Link Management Tools and Resources

This module contains tools and resources for parsing, resolving, and
validating markdown links and transclusions within Memory Bank files.

Total: 4 tools, 4 resources
- parse_file_links / parse_file_links_resource (cortex://links/parse/{file_name})
- resolve_transclusions / resolve_transclusions_resource (cortex://links/transclusions/{file_name})
- validate_links / validate_links_resource (cortex://links/validate)
- get_link_graph / get_link_graph_resource (cortex://links/graph)

This module re-exports MCP tools and resources from specialized operation
modules to provide a stable import path.
"""

from cortex.tools.linking.graph_operations import (
    get_link_graph,
    get_link_graph_resource,
)
from cortex.tools.linking.parser_operations import (
    parse_file_links,
    parse_file_links_resource,
)
from cortex.tools.linking.transclusion_operations import (
    resolve_transclusions,
    resolve_transclusions_resource,
)
from cortex.tools.linking.validation_operations import (
    validate_links,
    validate_links_resource,
)

__all__ = [
    "parse_file_links",
    "parse_file_links_resource",
    "resolve_transclusions",
    "resolve_transclusions_resource",
    "validate_links",
    "validate_links_resource",
    "get_link_graph",
    "get_link_graph_resource",
]
