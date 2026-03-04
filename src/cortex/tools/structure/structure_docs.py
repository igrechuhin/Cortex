# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Phase 8 structure tool docstrings (kept in separate module for file-size compliance)."""

CHECK_STRUCTURE_HEALTH_DOC = """Analyze project structure health and optionally perform cleanup operations.

    USE WHEN: User wants structure health check, user needs to fix
    structure issues, user requests structure validation, user wants
    cleanup actions.

    EXAMPLES: 'check structure health', 'fix structure issues',
    'validate project structure', 'perform structure cleanup'.

    RETURNS: JSON with health score, issues found, and cleanup results.

    Performs comprehensive health checks on the MCP Memory Bank project structure,
    verifying that all required directories exist, symlinks are valid, configuration
    files are present, and files are properly organized. Optionally performs cleanup
    actions to maintain structure integrity and archive stale content.

    Health checks validate:
    - Required directories (.cursor/, .cursor/memory-bank/, .cursor/plans/, etc.)
    - Symlink validity and targets (memory-bank/ → .cursor/memory-bank/)
    - Configuration files existence and validity (.cursor/structure.json)
    - File organization (plans in correct subdirectories, no orphaned files)
    - Memory bank file presence (projectBrief.md, activeContext.md, etc.)

    Cleanup actions (when perform_cleanup=True):
    - archive_stale: Move inactive plans older than stale_days to archived/
    - organize_plans: Categorize plans by status (active/completed/archived)
    - fix_symlinks: Repair broken Cursor symlinks (memory-bank/, rules/)
    - update_index: Refresh metadata index (.cortex/index.json)
    - remove_empty: Remove empty plan directories (active/, completed/, archived/)

    Args:
        perform_cleanup: Whether to perform cleanup actions in addition to health
            checks. Default: False (check-only mode)
        cleanup_actions: List of specific cleanup actions to perform. Valid values:
            ["archive_stale", "organize_plans", "fix_symlinks", "update_index",
            "remove_empty"]. If None, performs all cleanup actions. Example:
            ["archive_stale", "fix_symlinks"]
        stale_days: Number of days of inactivity before considering a plan file
            stale for archival. Based on file modification time. Default: 90.
            Example: 30 (archive plans inactive for 30+ days)
        dry_run: If True, previews cleanup actions without making changes. If False,
            executes cleanup actions. Default: True (safe preview mode).
            Example: False (execute cleanup)

    Returns:
        JSON string containing health report. See tool descriptor for full schema.

    Note:
        - Project root is resolved internally (MCP roots or current working directory).
        - This tool replaces the deprecated cleanup_project_structure tool
        - Use perform_cleanup=True to perform cleanup actions alongside health checks
        - Always run with dry_run=True first to preview changes before executing
        - The stale_days parameter uses file modification time (st_mtime),
          not access time
        - Cleanup actions are idempotent and safe to run multiple times
        - Health score formula: 100 - (10 × number_of_issues), minimum 0
        - Grade mapping: A=90-100, B=80-89, C=70-79, D=60-69, F=0-59
        - Status mapping: healthy=90-100, good=75-89, fair=60-74,
          warning=40-59, critical=0-39
        - If structure is not initialized, returns score=0, grade=F,
          status=not_initialized
"""

GET_STRUCTURE_INFO_DOC = """Get current project structure configuration, paths, and status information.

    USE WHEN: User needs structure paths, user wants structure
    configuration, user requests structure info, user needs path
    information.

    EXAMPLES: 'get structure info', 'show structure paths', 'get structure
    configuration', 'get memory bank path'.

    RETURNS: JSON with structure version, paths, configuration, and
    health status.

    Retrieves comprehensive information about the MCP Memory Bank project structure,
    including the structure version, all configured component paths (memory bank,
    plans, rules directories), configuration settings, existence status of each
    component, and a high-level health summary. Project root is resolved internally
    (MCP roots or current working directory); no parameters required.

    Args:
        None. Project root is resolved by the server (MCP roots or cwd).

    Returns:
        JSON string containing structure_info (paths, version, config) with a canonical
        status field.

    Example (success):
        {"status": "success", "structure_info": {"paths": {"memory_bank": "..."}, ...},
         "message": "✅ Structure information retrieved successfully"}

    Example (error):
        {"status": "error", "error": "Project root not found", "error_type": "ValueError"}

    Note:
        - This is a read-only tool that does not modify any files or directories
        - Use check_structure_health() for detailed analysis
        - All paths returned are absolute paths
"""
