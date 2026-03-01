"""Structure subpackage: project structure health and info.

Total: 2 tools
- check_structure_health (with optional perform_cleanup)
- get_structure_info
"""

from cortex.tools.structure.main import (
    build_health_result,
    check_structure_health,
    check_structure_health_resource,
    check_structure_initialized,
    find_stale_plans,
    get_project_root_resource,
    get_structure_info,
    get_structure_info_resource,
    invalidate_structure_resource_cache,
    move_stale_plans,
    perform_archive_stale,
    perform_cleanup_actions,
    perform_fix_symlinks,
    perform_remove_empty,
    perform_update_index,
    record_archive_action,
)

__all__ = [
    "build_health_result",
    "check_structure_health",
    "check_structure_health_resource",
    "check_structure_initialized",
    "find_stale_plans",
    "get_structure_info",
    "get_structure_info_resource",
    "get_project_root_resource",
    "invalidate_structure_resource_cache",
    "move_stale_plans",
    "perform_archive_stale",
    "perform_cleanup_actions",
    "perform_fix_symlinks",
    "perform_remove_empty",
    "perform_update_index",
    "record_archive_action",
]
