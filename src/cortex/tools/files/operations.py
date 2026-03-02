"""
File Operations Tools

This module re-exports the consolidated file management tool and read resource
for Memory Bank. Implementation is split across:
- crud_operations: manage_file, get_file_resource (entry points)
- manage_file_helpers: validation, logging, dispatch
- crud_flow: read/write handlers, execute_memory_bank_write
- metadata_operations: metrics, snapshots, metadata
- section_operations: section extraction

Total: 1 tool, 1 resource
- manage_file: Read/write/metadata operations (unified)
- get_file_resource: Read file via cortex://memory-bank/file/{file_name}
"""

from cortex.tools.files.crud_flow import (
    build_write_response,
    execute_memory_bank_write,
)
from cortex.tools.files.crud_operations import (
    MANAGE_FILE_INPUT_EXAMPLES,
    get_file_resource,
    manage_file,
)
from cortex.tools.files.metadata_operations import (
    compute_file_metrics,
    create_version_snapshot,
    update_file_metadata,
)
from cortex.tools.files.operation_helpers import FileOperation
from cortex.tools.files.section_operations import extract_sections

__all__ = [
    "MANAGE_FILE_INPUT_EXAMPLES",
    "FileOperation",
    "build_write_response",
    "compute_file_metrics",
    "create_version_snapshot",
    "execute_memory_bank_write",
    "extract_sections",
    "get_file_resource",
    "manage_file",
    "update_file_metadata",
]
